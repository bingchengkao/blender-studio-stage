# One-minute self-check: is this machine ready to work on this piece?
#   blender -b <piece.blend> --python-exit-code 1 --python selfcheck.py [-- --open]
# Runs with the person's own Blender preferences, never --factory-startup: checking them is the point.
# --open: when no Blender answers on the channel, open the piece in one. Only when they have no
# Blender open: one that has the piece but is not on the channel would leave two windows on one file.
# Each step prints OK or FAIL with the likely why in plain words; RECORD is what to keep in the note,
# RESULT the outcome. It leaves the piece as it was: the look value it moves is put back in any case,
# nothing is saved, and a stand-in camera for the headless frame exists only in this process.
# Verified on Blender 5.2.2 LTS (macOS), official MCP add-on 1.0.3, MCP server main@dbbf836.
import datetime, importlib, json, os, queue, re, shutil, subprocess, sys, tempfile, threading, time
from math import radians
import bpy
import numpy as np

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
PIECE = bpy.data.filepath
TMP = tempfile.mkdtemp(prefix="selfcheck_")
record = {"date": datetime.date.today().isoformat(), "blender": bpy.app.version_string}
failed = []
ch = None
now = "start"  # the step under way, named if the check itself breaks


class Stop(Exception):
    """A step the rest depends on failed."""


def say(ok, step, text):
    print(("OK    " if ok else "FAIL  ") + step + ": " + " ".join(str(text).split()), flush=True)
    if not ok:
        failed.append(step)
    return ok


def need(ok, step, text):
    if not say(ok, step, text):
        raise Stop


def finish():
    if ch is not None:
        ch.p.terminate()
    shutil.rmtree(TMP, ignore_errors=True)
    print("RECORD " + json.dumps(record, ensure_ascii=False), flush=True)
    print("RESULT " + ("all steps passed" if not failed else "failed: " + ", ".join(failed)), flush=True)
    sys.exit(1 if failed else 0)


# --- this Blender and its preferences --------------------------------------------------------

def read_manifest(folder):
    """The plain `key = "value"` lines of an add-on's manifest: all this needs, in any Python. The
    first of a name wins: top-level keys come before any [table] in TOML."""
    found = {}
    with open(os.path.join(folder, "blender_manifest.toml"), encoding="utf-8") as fh:
        for key, value in re.findall(r'^\s*(\w+)\s*=\s*["\']([^"\'\n]*)["\']', fh.read(), re.M):
            found.setdefault(key, value)
    return found


def manifest(ext_id):
    """The manifest of an enabled extension add-on with this id, from whichever repository."""
    for key in bpy.context.preferences.addons.keys():
        if key.startswith("bl_ext.") and key.rsplit(".", 1)[-1] == ext_id:
            mod = sys.modules.get(key) or importlib.import_module(key)
            return read_manifest(os.path.dirname(mod.__file__))
    return None


def version(text):
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3])


def check_blender():
    global now
    now = "this Blender"
    shipped = read_manifest(os.path.join(HERE, "studio_stage"))  # the panel add-on this plugin carries
    try:
        with open(os.path.join(HERE, "..", "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            record["plugin"] = json.load(fh)["version"]
    except (OSError, ValueError, KeyError):
        pass  # run from somewhere other than the plugin: nothing to record
    new_enough = bpy.app.version >= version(shipped["blender_version_min"])
    need(new_enough, "this Blender", "Blender %s" % bpy.app.version_string if new_enough else
         "Blender %s is older than the add-ons need (%s or newer): setup.md says what to do."
         % (bpy.app.version_string, shipped["blender_version_min"]))
    now = "add-ons"
    ok = True
    for ext_id, what in (("studio_stage", "the studio panel add-on"),
                         ("mcp", "the official MCP add-on (the channel's half inside Blender)")):
        m = manifest(ext_id)
        if m is None:
            ok &= say(False, "add-on " + ext_id, what + " is not installed or not enabled in this Blender. Blender keeps "
                      "add-ons per version, so a new or second Blender gets them again (setup.md).")
            continue
        record[ext_id] = m.get("version", "?")
        need_v = m.get("blender_version_min", "0")
        if bpy.app.version < version(need_v):
            ok &= say(False, "add-on " + ext_id, "%s %s needs Blender %s or newer; this one is %s."
                      % (what, record[ext_id], need_v, bpy.app.version_string))
        elif ext_id == "studio_stage" and record[ext_id] != shipped.get("version"):
            ok &= say(False, "add-on " + ext_id, "%s in this Blender is %s, but the plugin carries %s, so the "
                      "panel's Export would run other code than yours: install the plugin's copy again (setup.md)."
                      % (what, record[ext_id], shipped.get("version")))
        else:
            say(True, "add-on " + ext_id, "%s, made for Blender %s and newer" % (record[ext_id], need_v))
    now = "online access"
    online = bpy.context.preferences.system.use_online_access
    ok &= say(online, "online access", "on" if online else
              "off in Blender's preferences (System > Network). The MCP add-on opens no connection without it, and "
              "decides when Blender starts: turn it on, then they save, close and reopen Blender.")
    return ok


# --- graphics and one frame, headless ----------------------------------------------------------

def check_frame():
    global now
    now = "graphics"
    cp = bpy.context.preferences.addons["cycles"].preferences
    gpus = []
    for kind in [t[0] for t in cp.get_device_types(bpy.context) if t[0] != "NONE"]:
        gpus += ["%s (%s)" % (d.name, kind) for d in cp.get_devices_for_type(kind) if d.type != "CPU"]
    record["gpu"] = ", ".join(gpus) or "none found for Cycles: it would render on the CPU"
    say(True, "graphics", record["gpu"])

    now = "one frame"
    sc, r = bpy.context.scene, bpy.context.scene.render
    stand_in = ""
    if sc.camera is None:  # a fresh piece has none yet; this one is never saved
        cam = bpy.data.objects.new("selfcheck camera", bpy.data.cameras.new("selfcheck camera"))
        sc.collection.objects.link(cam)
        cam.location, cam.rotation_euler = (0.0, -8.0, 2.0), (radians(80), 0.0, 0.0)
        sc.camera, stand_in = cam, ", from a stand-in camera (the piece has none yet)"
    sc.frame_set((sc.frame_start + sc.frame_end) // 2)
    t = time.perf_counter()
    try:
        bpy.ops.render.render()
    except RuntimeError as ex:
        say(False, "one frame", "Blender could not render it headless: %s" % ex)
        return
    secs = round(time.perf_counter() - t, 1)
    size = "%dx%d" % (r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100)
    device = ""
    if r.engine == "CYCLES":
        on_gpu = sc.cycles.device == "GPU" and cp.compute_device_type != "NONE" and cp.has_active_device()
        device = " on the GPU" if on_gpu else " on the CPU"
    record["frame"] = "%s s, %s%s, %s, the file on disk%s" % (secs, r.engine, device, size, stand_in)
    say(True, "one frame", record["frame"] + (" (the first Cycles render on a machine also prepares the graphics card)"
                                              if r.engine == "CYCLES" else ""))


# --- the channel -----------------------------------------------------------------------------

def registration():
    d = os.path.dirname(PIECE)
    while True:
        path = os.path.join(d, ".mcp.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                server = json.load(fh).get("mcpServers", {}).get("blender")
            if server:
                return path, server
        if os.path.dirname(d) == d:
            return None, None
        d = os.path.dirname(d)


class Channel:
    """Starts the channel's server the way Claude Code would, and speaks MCP to it over stdio."""

    def __init__(self, spec):
        env = dict(os.environ, **{k: os.path.expandvars(v) for k, v in spec.get("env", {}).items()})
        cmd = [os.path.expandvars(a) for a in [spec["command"]] + spec.get("args", [])]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8", errors="replace", env=env)
        self.out, self.err, self.n = queue.Queue(), [], 0
        threading.Thread(target=self._pump, args=(self.p.stdout, self.out.put), daemon=True).start()
        self.err_pump = threading.Thread(target=self._pump, args=(self.p.stderr, self.err.append), daemon=True)
        self.err_pump.start()

    @staticmethod
    def _pump(stream, sink):
        for line in stream:
            sink(line)
        sink(None)

    def _send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def request(self, method, params, timeout):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        end = time.time() + timeout
        while True:
            line = self.out.get(timeout=max(0.1, end - time.time()))  # queue.Empty when it does not answer
            if line is None:
                self.err_pump.join(timeout=5)  # its last words explain why
                raise EOFError("".join(l for l in self.err if l)[-600:])
            msg = json.loads(line)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "error"))
                return msg["result"]

    def run(self, code, timeout=30):
        """Python run in the open Blender; returns its `result`, or raises RuntimeError with the reason."""
        res = self.request("tools/call", {"name": "execute_blender_code", "arguments": {"code": code}}, timeout)
        body = res.get("structuredContent")
        if body is None:
            text = "".join(c.get("text", "") for c in res.get("content", []))
            try:
                body = json.loads(text)
            except ValueError:
                body = {"status": "error", "message": text}
        if res.get("isError") or body.get("status") != "ok":
            raise RuntimeError(body.get("message", "unknown error"))
        return body["result"]


def start_channel():
    global ch, now
    now = "channel registered"
    path, spec = registration()
    need(spec is not None, "channel registered", path if spec else
         "no .mcp.json with a server named `blender` in the piece's folder or above it (setup.md).")
    pin = re.search(r"@([0-9a-f]{7,40})", " ".join(spec.get("args", [])))
    record["channel"] = pin.group(1)[:7] if pin else "not pinned"
    now = "channel starts"
    try:
        ch = Channel(spec)
        ch.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "selfcheck", "version": "1"}}, timeout=180)
        ch._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = [t["name"] for t in ch.request("tools/list", {}, timeout=30)["tools"]]
    except FileNotFoundError:
        need(False, "channel starts", "`%s` was not found: uv is not installed, or not at that path." % spec["command"])
    except (EOFError, queue.Empty, OSError, ValueError, RuntimeError) as ex:
        msg = str(ex).strip() or "no answer"
        why = ("Probably git is missing, or there was no network to fetch this version the first time. "
               if "git" in msg.lower() else "")
        need(False, "channel starts", "the channel's server did not start. " + why + "It said: " + msg[-400:])
    say(True, "channel starts", "%d tools, pinned at %s" % (len(tools), record["channel"]))
    need("execute_blender_code" in tools, "channel tools",
         "has the tool that runs Python in Blender" if "execute_blender_code" in tools else
         "the channel's tools have changed since this check was written: this check is out of date; "
         "the channel may well be fine.")


WHO = 'import bpy\nresult = {"file": bpy.data.filepath, "dirty": bpy.data.is_dirty, "version": bpy.app.version_string}'


def reach():
    """(who, why): who answered on the channel, or why nobody did."""
    try:
        return ch.run(WHO, timeout=15), ""
    except queue.Empty:
        return None, "busy"
    except RuntimeError as ex:
        return None, " ".join(str(ex).split())[:300]


def open_piece():
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([bpy.app.binary_path, PIECE], **kw)


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def check_reach():
    global now
    now = "reach Blender"
    who, why = reach()
    opened = False
    if who is None and why != "busy" and "--open" in ARGS:
        open_piece()
        opened = True
        end = time.time() + 60
        while who is None and why != "busy" and time.time() < end:
            time.sleep(1)
            who, why = reach()
    if who is None:
        if why == "busy":
            text = ("something holds the channel's port but does not answer like Blender: another program, or "
                    "another Blender MCP add-on, may be using it.")
        elif opened:
            text = "opened the piece, but its Blender did not answer through the channel within a minute: " + why
        else:
            text = ("no Blender answered through the channel. If the piece is open, its Blender has not opened the "
                    "channel: they save, close and reopen it (the MCP add-on starts with Blender). If no Blender is "
                    "open, run this again with `-- --open`.")
        need(False, "reach Blender", text)
    say(True, "reach Blender", "Blender %s answered%s" % (who["version"], " (opened it)" if opened else ""))
    now = "which Blender"
    need(who["version"] == bpy.app.version_string, "which Blender",
         "the channel reaches the Blender this check ran in" if who["version"] == bpy.app.version_string else
         "the channel reaches Blender %s, but this check ran in %s: two Blenders are installed. Open the piece in "
         "the one the add-ons were checked in, or run this check with the other." % (who["version"], bpy.app.version_string))
    now = "which file"
    same = bool(who["file"]) and same_file(who["file"], PIECE)
    need(same, "which file", "the open Blender has this piece" if same else
         "the Blender on the channel has %s open, not this piece. Nothing was changed." % (who["file"] or "an unsaved file"))
    return who, opened


# --- move one look value and watch the picture -------------------------------------------------

VIEW = '''
import bpy
def view():
    for win in bpy.context.window_manager.windows:
        areas = [a for a in win.screen.areas if a.type == "VIEW_3D"]
        if areas:
            return win, max(areas, key=lambda a: a.width * a.height)
    return None, None
def shot(path):
    win, area = view()
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
def put(key, value, compositor=None):
    sc = bpy.context.scene
    sc[key] = value
    sc.update_tag()  # a value set from Python is neither re-evaluated nor redrawn on its own
    area = view()[1]
    if compositor:
        area.spaces.active.shading.use_compositor = compositor
    area.tag_redraw()
'''

STATE = VIEW + '''
sc = bpy.context.scene
def ranged(k):
    ui = sc.id_properties_ui(k).as_dict()
    lo, hi = ui.get("soft_min", ui.get("min")), ui.get("soft_max", ui.get("max"))
    return (lo, hi) if lo is not None and hi is not None and -1e6 < lo < hi < 1e6 else None
studio = sc["studio"] if "studio" in sc else {}
keys = [k for k in studio.get("controls", {}).keys() if k in sc and isinstance(sc[k], float) and ranged(k)]
key = "look_post_exposure" if "look_post_exposure" in keys else (keys[0] if keys else None)
win, area = view()
result = {"key": key, "value": sc[key] if key else None, "range": ranged(key) if key else None,
          "shading": area.spaces.active.shading.type if area else None,
          "compositor": area.spaces.active.shading.use_compositor if area else None,
          "camera": sc.camera is not None, "playing": win.screen.is_animation_playing if win else False}
'''


def pixels():
    path = os.path.join(TMP, "view.png")
    ch.run(VIEW + "shot(%r)\nresult = {}" % path)
    im = bpy.data.images.load(path)
    a = np.empty(len(im.pixels), dtype=np.float32)
    im.pixels.foreach_get(a)
    a = a.reshape(im.size[1], im.size[0], 4)[..., :3]
    bpy.data.images.remove(im)
    return a


class Resized(Exception):
    pass


def changed(a, b):
    """Share of the view's pixels that visibly differ."""
    if a.shape != b.shape:
        raise Resized
    return float((np.abs(a - b).max(axis=-1) > 0.02).mean())


def settled(limit):
    """The view once it stops changing: a piece just opened, or just changed, is still drawing."""
    last, end = pixels(), time.perf_counter() + limit
    while time.perf_counter() < end:
        time.sleep(0.3)
        a = pixels()
        if changed(a, last) < 0.001:
            return a
        last = a
    return last


def check_knob(who, opened):
    global now
    now = "a look value"
    state = ch.run(STATE)
    end = time.time() + (10 if opened else 0)  # a piece just opened enters the studio layout a moment later
    while state["shading"] != "RENDERED" and time.time() < end:
        time.sleep(0.5)
        state = ch.run(STATE)
    need(state["key"] is not None, "a look value", state["key"] or "the piece has no number control with a range to move")
    need(not state["playing"], "paused", "the animation is paused" if not state["playing"] else
         "the animation is playing: pause it, then run this again")
    need(state["shading"] == "RENDERED", "rendered view", "the view shows the rendered picture"
         if state["shading"] == "RENDERED" else "the view is not showing the rendered picture (full Blender?); "
         "back in the studio layout it does")

    now = "move " + state["key"]
    key, old = state["key"], state["value"]
    lo, hi = state["range"]
    new = old + (hi - lo) / 3 if old + (hi - lo) / 3 <= hi else old - (hi - lo) / 3
    # Post is drawn in camera view only; a fresh piece has no camera yet, so for the test it is drawn always.
    comp = "ALWAYS" if not state["camera"] and state["compositor"] == "CAMERA" else None
    limit = 15 if bpy.context.scene.render.engine == "CYCLES" else 5
    t_first, frac = None, 0.0
    try:
        base = settled(2 * limit)
        ch.run(VIEW + "put(%r, %r, %r)\nresult = {}" % (key, float(new), comp))
        t0 = time.perf_counter()
        while t_first is None and time.perf_counter() - t0 < limit:
            if changed(pixels(), base) > 0.01:
                t_first = round(time.perf_counter() - t0, 1)
        frac = changed(settled(limit), base)
    except Resized:
        say(False, now, "the Blender window changed size during the check: run it again")
    finally:
        try:
            ch.run(VIEW + "put(%r, %r, %r)\nresult = {}" % (key, float(old), state["compositor"] if comp else None))
            after = ch.run('import bpy\nresult = {"value": bpy.context.scene[%r], "dirty": bpy.data.is_dirty}' % key)
        except (RuntimeError, queue.Empty, EOFError, OSError) as ex:
            need(False, "put it back", "could not reach Blender to put %s back: set it to %r by hand (%s)" % (key, old, ex))
    if "move " + key not in failed:
        moved = t_first is not None and frac > 0.01  # a restarting render flickers; the settled picture decides
        record["drag"] = ("picture changed within %s s, seen through the channel" % t_first) if moved \
            else "no change within %s s" % limit
        say(moved, "move " + key, ("%g -> %g: %d%% of the view changed, the first change within %s s "
                                                 "(screenshots through the channel, so slower than what they see)"
                                                 % (old, new, round(frac * 100), t_first)) if moved else
            "%g -> %g: the picture did not change within %s s. The view may not be redrawing, or this value drives "
            "nothing." % (old, new, limit))
    restored = after["value"] == old and after["dirty"] == who["dirty"]
    say(restored, "put it back", "%g again, and the file's saved state as before" % old if restored else
        "%s is %r (was %r), saved state %s (was %s)" % (key, after["value"], old, after["dirty"], who["dirty"]))


def main():
    global now
    now = "the piece"
    need(bool(PIECE), "the piece", PIECE or "Blender was started without a saved .blend: run it as `blender -b <piece.blend> ...`")
    prefs_ok = check_blender()
    check_frame()
    start_channel()
    if not prefs_ok:
        print("SKIP  reach Blender: this Blender's preferences have to be fixed first (above)", flush=True)
        return
    who, opened = check_reach()
    check_knob(who, opened)


try:
    main()
except Stop:
    pass
except Exception as ex:  # the check itself broke: say where, not a traceback
    say(False, now, "the check itself broke here (%s: %s)" % (type(ex).__name__, ex))
finish()
