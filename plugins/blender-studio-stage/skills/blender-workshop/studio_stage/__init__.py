# Studio Stage: what a person sees when they open a studio piece in Blender.
#
# A piece is a scene carrying a "studio" property: {"lang", "mode", "controls"}. Its look values
# are plain scene custom properties named look_*: a number, a colour (float array, colour subtype),
# a choice (int with items) or an on/off. Range, items and hint live in each property's UI data,
# label / group / rank in studio["controls"]. Rank 1-3 is the lowest control mode that lays it
# open; in a lower one it folds under its group's More, and a look value not listed under Other's.
# Rank 0 is the post set, open in every mode. Nothing here is needed to render or check a piece.
#
# Opening a piece strips the window to the camera view and this panel, and keeps it there: the view
# cannot be orbited or clicked into, only zoomed. "Open full Blender" undoes all of it. Scripts run
# through the channel still select freely; what they leave selected is cleared between calls.
#
# Export runs export.py beside this file in a headless Blender, on a copy saved when it is pressed.
# Verified on Blender 5.2.2 LTS, macOS.
import functools
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zlib
from math import sqrt

import bpy
from bpy.app.handlers import persistent
from bpy_extras.view3d_utils import location_3d_to_region_2d

CATEGORY = "Studio"
PREVIOUS = ".previous"  # file name of the look kept automatically before another is loaded

STRINGS = {
    "en": {
        "save": "Save", "saved": "Saved", "fit": "Whole frame", "time": "Time",
        "of_seconds": "/ {total} s", "looks": "Saved looks", "save_look": "Save the current look",
        "previous": "Previous", "version": "Version {n}", "name": "Name", "ok_save": "Save",
        "delete": "Delete “{name}”?", "ok_delete": "Delete", "full": "Open full Blender",
        "back": "Back to the studio layout", "need_save": "Save the file first",
        "tip_save": "Save the piece's file", "tip_fit": "Show the whole picture again",
        "tip_save_look": "Keep the values on screen under a name",
        "tip_load": "Bring this look back; what is on screen now is kept as Previous",
        "tip_delete": "Delete this saved look", "tip_full": "Show all of Blender",
        "tip_back": "Back to just the picture and this panel",
        "export": "Export", "size": "Size", "quality": "Quality", "export_go": "Export",
        "f_mp4": "MP4", "f_prores": "ProRes", "f_png-sequence": "PNG sequence", "f_frame": "This frame",
        "f_png": "PNG", "f_tiff": "TIFF", "f_jpeg": "JPEG",
        "tip_f_mp4": "A video that plays anywhere", "tip_f_prores": "For editing: high quality, large files",
        "tip_f_png-sequence": "Every frame as an image of its own", "tip_f_frame": "The frame on screen now, as one image",
        "tip_f_png": "An image with nothing lost", "tip_f_tiff": "For print", "tip_f_jpeg": "Small, for sending",
        "s_half": "Half", "s_full": "Full", "s_double": "Double",
        "q_draft": "Draft", "q_final": "Final", "q_finer": "Finer",
        "tip_q_draft": "Half size and rough, to see the motion quickly",
        "tip_q_final": "The quality set for delivery",
        "tip_q_finer": "Twice the samples: less noise, up to twice the time",
        "tip_export": "Render what is on screen now into the exports folder",
        "snapshot": "Exports what is on screen now; keep tuning if you like",
        "cancel": "Cancel",
        "preparing": "Exporting: getting ready…", "exporting": "Exporting {done} / {total}",
        "left_min": " · about {m} min {s} s left", "left_s": " · about {s} s left",
        "slower": "The picture here is slower while exporting",
        "done": "Exported:", "open_folder": "Show in folder", "failed": "Export failed: {why}",
        "more": "More ({n})", "other": "Other", "tip_more": "Controls kept folded away; click to open or fold them",
    },
    "zh-Hant": {
        "save": "存檔", "saved": "已存檔", "fit": "回到整張", "time": "時間",
        "of_seconds": "/ {total} 秒", "looks": "存起來的樣子", "save_look": "把現在的樣子存起來",
        "previous": "剛才", "version": "版本 {n}", "name": "名字", "ok_save": "存起來",
        "delete": "刪掉「{name}」？", "ok_delete": "刪掉", "full": "打開完整的 Blender",
        "back": "回到 studio 版面", "need_save": "先把檔案存起來",
        "tip_save": "把作品存檔", "tip_fit": "把整張畫面放回來",
        "tip_save_look": "把畫面上的數值取個名字存起來",
        "tip_load": "叫回這個樣子；現在的樣子會留成「剛才」",
        "tip_delete": "刪掉這個存起來的樣子", "tip_full": "打開完整的 Blender",
        "tip_back": "回到只有畫面和這個面板",
        "export": "導出", "size": "尺寸", "quality": "品質", "export_go": "導出",
        "f_png-sequence": "PNG 序列", "f_frame": "這一格",
        "tip_f_mp4": "一般影片，哪裡都能播", "tip_f_prores": "剪輯用的高畫質影片，檔案很大",
        "tip_f_png-sequence": "每一格存成一張圖", "tip_f_frame": "畫面上這一格，存成一張圖",
        "tip_f_png": "不失真的圖", "tip_f_tiff": "印刷用", "tip_f_jpeg": "檔案小，傳給人看",
        "s_half": "一半", "s_full": "原尺寸", "s_double": "兩倍",
        "q_draft": "草稿", "q_final": "正式", "q_finer": "更細",
        "tip_q_draft": "半尺寸、算得粗，先看動態和節奏",
        "tip_q_final": "交件的品質",
        "tip_q_finer": "取樣加倍：雜點更少，時間最多兩倍",
        "tip_export": "把畫面上這一刻的樣子算進 exports 資料夾",
        "snapshot": "導出按下那一刻的樣子，可以繼續調",
        "cancel": "取消",
        "preparing": "導出中：準備中…", "exporting": "導出中 {done}／{total} 格",
        "left_min": "・約剩 {m} 分 {s} 秒", "left_s": "・約剩 {s} 秒",
        "slower": "導出時，這裡的畫面會變慢",
        "done": "導出好了：", "open_folder": "打開資料夾", "failed": "導出失敗：{why}",
        "more": "更多（{n}）", "other": "其他", "tip_more": "平常收起來的旋鈕，點一下打開或摺起來",
    },
}

# studio: the layout is on · duration: the time slider's range · looks: cached list of saved
# looks · fit: what the frame was last fitted to · more: groups whose More is open, till a file opens.
_state = {"studio": False, "duration": None, "looks": None, "fit": None, "more": set()}


# --- the piece ------------------------------------------------------------------------------

def is_piece(scene):
    return scene is not None and "studio" in scene


def _ui_data(scene, key):
    try:
        return scene.id_properties_ui(key).as_dict()
    except TypeError:  # a kind of property that carries no UI data
        return {}


def text(scene, key, /, **kw):  # positional: a problem's own fields may be called key or name
    table = dict(STRINGS["en"])
    if is_piece(scene):
        studio = scene["studio"]
        table.update(STRINGS.get(studio.get("lang", "en"), {}))
        if "ui" in studio:  # a language not built in: the piece carries its own words
            table.update(studio["ui"].to_dict())
    try:
        return table[key].format(**kw)
    except (KeyError, IndexError, ValueError):  # a piece's own words with other placeholders
        return STRINGS["en"][key].format(**kw)


def control_groups(scene):
    """[(group, shown, more, is_post)] in the order the controls were written, post last; shown
    and more are [(key, label)], more what the control mode leaves out. Look values with no control
    go under Other's more, so none is out of reach; one with no label goes by its hint."""
    studio = scene["studio"]
    mode = int(studio.get("mode", 1))
    controls = studio.get("controls", {})

    def label(key, c):
        return (c.get("label") or _ui_data(scene, key).get("description")
                or key.removeprefix("look_").replace("_", " "))

    groups = {}
    for key, c in controls.items():
        rank = int(c.get("rank", 1))
        if key in scene:
            g = groups.setdefault(c.get("group", ""), ([], [], rank == 0))
            g[0 if rank <= mode else 1].append((key, label(key, c)))
    other = text(scene, "other")
    for key in scene.keys():
        if key.startswith("look_") and key not in controls:
            groups.setdefault(other, ([], [], False))[1].append((key, label(key, {})))
    ordered = [(name, shown, more, post) for name, (shown, more, post) in groups.items()]
    return [g for g in ordered if not g[3]] + [g for g in ordered if g[3]]


def redraw_all():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def touch(scene):
    # A value set from Python skips the update a dragged slider sends: ask for it ourselves.
    scene.update_tag()
    redraw_all()


# --- time, in seconds -----------------------------------------------------------------------

def _fps(scene):
    return scene.render.fps / scene.render.fps_base


def _get_time(self):
    s = bpy.context.scene
    return (s.frame_current - s.frame_start) / _fps(s)


def _set_time(self, value):
    s = bpy.context.scene
    s.frame_current = min(s.frame_end, s.frame_start + round(value * _fps(s)))


def ensure_time_prop(scene):
    # A slider's range is fixed when it is registered, so it is registered again per length.
    duration = round((scene.frame_end - scene.frame_start) / _fps(scene), 3)
    if duration == _state["duration"]:
        return
    _state["duration"] = duration
    top = max(duration, 0.001)
    bpy.types.WindowManager.studio_time = bpy.props.FloatProperty(
        name="Time", min=0.0, max=top, soft_min=0.0, soft_max=top, precision=1, step=10,
        get=_get_time, set=_set_time)
    redraw_all()  # buttons still pointing at the old property are rebuilt at once


# --- the studio layout ----------------------------------------------------------------------

def main_window():
    windows = bpy.context.window_manager.windows
    return windows[0] if windows else None


def view3d_area(screen):
    areas = [a for a in screen.areas if a.type == "VIEW_3D"]
    return max(areas, key=lambda a: a.width * a.height) if areas else None


def in_studio(context):
    return _state["studio"] and context.screen is not None and context.screen.show_fullscreen


def select_toggles(space):
    # One per kind of object; reading them from the space keeps up with kinds Blender adds.
    return [p.identifier for p in space.bl_rna.properties if p.identifier.startswith("show_object_select_")]


def deselect_all(view_layer):
    for o in [o for o in view_layer.objects if o.select_get()]:
        o.select_set(False)
    if view_layer.objects.active is not None:
        view_layer.objects.active = None


def enter_studio():
    win = main_window()
    area = view3d_area(win.screen) if win else None
    if area is None:
        return
    if win.screen.show_fullscreen:
        # Maximized and fullscreen look the same from Python, and a maximized view refuses to go
        # fullscreen: step back to the normal layout first.
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.back_to_previous()
        area = view3d_area(win.screen)
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=True)
    area = view3d_area(win.screen)
    space = area.spaces.active
    space.shading.type = "RENDERED"
    space.shading.use_compositor = "CAMERA"
    space.overlay.show_overlays = False
    space.show_gizmo = False
    space.show_region_toolbar = False
    space.show_region_header = False
    space.show_region_tool_header = False
    space.show_region_ui = True
    space.lock_camera = False  # zooming must never move the real camera
    for name in select_toggles(space):
        setattr(space, name, False)  # a click picks nothing; scripts still select
    win.screen.use_play_properties_editors = True  # the time slider follows playback
    _state["studio"] = True
    deselect_all(bpy.context.view_layer)
    fit_camera()
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.5)


def leave_studio():
    _state["studio"] = False
    win = main_window()
    area = view3d_area(win.screen) if win else None
    if area is None:
        return
    if win.screen.show_fullscreen:
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.back_to_previous()
        area = view3d_area(win.screen)
    space = area.spaces.active
    space.overlay.show_overlays = True
    space.show_gizmo = True
    space.show_region_toolbar = True
    space.show_region_header = True
    space.show_region_tool_header = True
    for name in select_toggles(space):
        setattr(space, name, True)


def _fit_key(scene):
    r = scene.render
    return scene.camera.name, r.resolution_x * r.pixel_aspect_x, r.resolution_y * r.pixel_aspect_y


def fit_camera():
    win = main_window()
    area = view3d_area(win.screen) if win else None
    scene = bpy.context.scene
    if area is None or scene.camera is None:
        return
    _state["fit"] = _fit_key(scene)
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "CAMERA"
    r3d.view_camera_offset = (0.0, 0.0)
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.view3d.view_center_camera()
    # The sidebar floats over the picture: shrink the frame and shift it into the space beside it.
    # Projections refresh only when the view draws, so each step measures after a redraw.
    bpy.app.timers.register(functools.partial(_fit_step, 0), first_interval=0.1)


def _frame_box(scene, region, r3d):
    cam = scene.camera
    pts = [location_3d_to_region_2d(region, r3d, cam.matrix_world @ v) for v in cam.data.view_frame(scene=scene)]
    if None in pts:
        return None
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)


def _fit_step(step, probe=None):
    # Looks the view up again every step: the layout may have changed since the last one.
    win = main_window()
    area = view3d_area(win.screen) if win else None
    scene = bpy.context.scene
    if area is None or scene.camera is None or scene.camera.type != "CAMERA":
        return None
    region = next(r for r in area.regions if r.type == "WINDOW")
    ui = next(r for r in area.regions if r.type == "UI")
    r3d = area.spaces.active.region_3d
    box = _frame_box(scene, region, r3d)
    if box is None or box[2] <= 0 or box[3] <= 0:
        return None
    margin = 24
    covered = max(0, region.x + region.width - ui.x) if area.spaces.active.show_region_ui else 0
    want_w = max(1, region.width - covered - 2 * margin)
    want_h = max(1, region.height - 2 * margin)
    cx, cy, w, h = box
    if step == 0:  # zoom so the whole frame fits
        fac = (sqrt(2) + r3d.view_camera_zoom / 50) ** 2 / 4 * min(want_w / w, want_h / h)
        r3d.view_camera_zoom = (2 * sqrt(fac) - sqrt(2)) * 50
    elif step == 1:  # learn how far one unit of offset moves the frame on this screen
        probe = (cx, cy)
        r3d.view_camera_offset = (0.1, 0.1)
    else:  # centre it in the free space
        rate_x, rate_y = (cx - probe[0]) / 0.1, (cy - probe[1]) / 0.1
        target_x, target_y = margin + want_w / 2, margin + want_h / 2
        r3d.view_camera_offset = (0.1 + (target_x - cx) / rate_x if rate_x else 0.0,
                                  0.1 + (target_y - cy) / rate_y if rate_y else 0.0)
        area.tag_redraw()
        return None
    area.tag_redraw()
    bpy.app.timers.register(functools.partial(_fit_step, step + 1, probe), first_interval=0.1)
    return None


def _tick():
    # Runs while a piece is open, never in the middle of a script.
    scene = bpy.context.scene
    if not is_piece(scene):
        return None
    ensure_time_prop(scene)
    if not _state["studio"]:
        return 0.5
    win = main_window()
    if win is None or not win.screen.show_fullscreen:
        leave_studio()  # they left some other way (Ctrl+Option+Space): undo the rest of it too
        return 0.5
    if bpy.context.mode == "OBJECT":
        deselect_all(bpy.context.view_layer)  # what a script left selected, a stray key would move
    cam = scene.camera
    if cam is not None and cam.type == "CAMERA":
        if cam.data.passepartout_alpha < 1.0:
            cam.data.passepartout_alpha = 1.0  # outside the frame is not the picture: black
        if _fit_key(scene) != _state["fit"]:
            fit_camera()  # a new camera or picture size
        area = view3d_area(win.screen)
        r3d = area.spaces.active.region_3d if area else None
        if r3d and r3d.view_perspective != "CAMERA":
            r3d.view_perspective = "CAMERA"  # a key we do not guard (number pad) left the camera
    return 0.5


# --- saved looks ----------------------------------------------------------------------------

def looks_dir():
    return os.path.join(os.path.dirname(bpy.data.filepath), "looks") if bpy.data.filepath else None


def look_path(name):
    return os.path.join(looks_dir(), name + ".json")


def _natural(name):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def saved_looks():
    """(names, has_previous), read from disk once and kept until a look is written or deleted."""
    if _state["looks"] is None:
        d = looks_dir()
        files = os.listdir(d) if d and os.path.isdir(d) else []
        names = [f[:-5] for f in files if f.endswith(".json") and not f.startswith(".")]
        _state["looks"] = (sorted(names, key=_natural), PREVIOUS + ".json" in files)
    return _state["looks"]


def write_look(scene, name):
    values = {}
    for k in (k for k in scene.keys() if k.startswith("look_")):
        v = scene[k]
        v = v.to_list() if hasattr(v, "to_list") else v
        if isinstance(v, (int, float, str)) or (isinstance(v, list) and all(isinstance(x, (int, float)) for x in v)):
            values[k] = v
    body = json.dumps(values, ensure_ascii=False, indent=2)  # before opening: no half-written file
    os.makedirs(looks_dir(), exist_ok=True)
    with open(look_path(name), "w", encoding="utf-8") as fh:
        fh.write(body)
    _state["looks"] = None


def apply_look(scene, data):
    for k, v in data.items():
        if not k.startswith("look_") or k not in scene:
            continue
        old = scene[k]
        try:
            # Same type in, or the property is replaced and loses its UI data: a choice its items,
            # an on/off its checkbox.
            if hasattr(old, "to_list"):  # an array (a colour): filled in place
                if isinstance(v, list) and len(v) == len(old):
                    old[:] = v
            elif isinstance(old, bool):  # before int: a bool is an int to Python
                scene[k] = bool(v)
            elif isinstance(old, float):
                scene[k] = float(v)
            elif isinstance(old, int):
                v = int(round(v))
                items = _ui_data(scene, k).get("items")
                if not items or v in [item[-1] for item in items]:  # a choice takes only its own
                    scene[k] = v
            elif isinstance(old, str) and isinstance(v, str):
                scene[k] = v
        except (TypeError, ValueError):
            pass  # a value that no longer fits is left as it is


# --- export ---------------------------------------------------------------------------------
# The panel runs the script the model runs (export.py beside this file) in a headless Blender, on a
# copy saved the moment Export is pressed: tuning can go on meanwhile. The defect check is the
# model's (check.py); the panel does not stop on it.

HERE = os.path.dirname(os.path.abspath(__file__))
FORMATS = ("mp4", "prores", "png-sequence", "frame")
FORMATS_STILL = ("png", "tiff", "jpeg")
SIZES = {"half": 0.5, "full": 1.0, "double": 2.0}
QUALITIES = ("draft", "final", "finer")
_pick = {"format": None, "size": "full", "quality": "final"}  # this session's choices; never in the file
# state: idle · exporting · done · failed
_job = {"state": "idle", "proc": None}


def is_still(scene):
    return scene.frame_end <= scene.frame_start


def picked_format(scene):
    formats = FORMATS_STILL if is_still(scene) else FORMATS
    return _pick["format"] if _pick["format"] in formats else formats[0]


def export_size(scene):
    r = scene.render
    scale = SIZES[_pick["size"]] * (0.5 if _pick["quality"] == "draft" else 1.0)
    w = max(2, round(r.resolution_x * r.resolution_percentage / 100 * scale))
    h = max(2, round(r.resolution_y * r.resolution_percentage / 100 * scale))
    if picked_format(scene) in ("mp4", "prores"):
        w, h = w + w % 2, h + h % 2
    return w, h


def _spawn(*args):
    """A headless Blender with no add-ons and no scripts, as delivery sees the piece."""
    hidden = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}  # no console popping up
    proc = subprocess.Popen([bpy.app.binary_path, "-b", "--factory-startup", "-Y", *args],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **hidden)
    lines = queue.Queue()

    def pump():
        for line in proc.stdout:
            lines.put(line.rstrip("\n"))
    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    _job.update(proc=proc, lines=lines, reader=reader, tail=[])


def _watch():
    if not bpy.app.timers.is_registered(_job_tick):
        bpy.app.timers.register(_job_tick, first_interval=0.3, persistent=True)  # outlives opening a file


def _end_job(state, **kw):
    _job.update(state=state, proc=None, **kw)
    shutil.rmtree(_job.get("tmp") or "", ignore_errors=True)
    _job["tmp"] = None


def _remove_partial():
    """What this export wrote before it stopped: export.py renders into <out>.part and renames it only
    when complete, so a finished file is never touched here."""
    part = (_job.get("out") or "") + ".part"
    for path in (part + ".mp4", part + ".mov", part + ".png", part + ".tif", part + ".jpg"):
        if os.path.isfile(path):
            os.remove(path)
    shutil.rmtree(part, ignore_errors=True)


def start_export(scene):
    """Saves what is on screen, saved or not, and starts rendering it. Returns why it could not, or None."""
    folder = os.path.join(os.path.dirname(bpy.data.filepath), "exports")
    try:
        os.makedirs(folder, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="studio_export_")
    except OSError as ex:
        return str(ex)
    copy = os.path.join(tmp, os.path.basename(bpy.data.filepath))
    try:
        bpy.ops.wm.save_as_mainfile(filepath=copy, copy=True)
    except RuntimeError as ex:
        shutil.rmtree(tmp, ignore_errors=True)
        return str(ex)
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    base = "%s_%s%s" % (stem, time.strftime("%m%d-%H%M"), "_draft" if _pick["quality"] == "draft" else "")
    taken = os.listdir(folder)
    n, name = 1, base
    while any(f == name or f.startswith(name + ".") for f in taken):  # twice in a minute
        n += 1
        name = "%s-%d" % (base, n)
    out = os.path.join(folder, name)
    _job.update(state="exporting", tmp=tmp, out=out, result=None, why="", started=time.time(), done=0, total=0)
    _spawn(copy, "--python-exit-code", "1", "--python", os.path.join(HERE, "export.py"), "--",
           "--format", picked_format(scene), "--size", _pick["size"], "--quality", _pick["quality"],
           "--out", out, "--frame", str(scene.frame_current))
    _watch()
    return None


def cancel_export():
    proc = _job.get("proc")
    running = proc is not None and proc.poll() is None
    if running:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    if proc is not None:
        _job["reader"].join(timeout=2)
        _read_lines()  # stopped at once, or crashed: it may have claimed its .part before the panel read so
    if _job["state"] == "exporting" and _job["total"] and _job["done"] < _job["total"]:
        _remove_partial()  # a half-written film is worse than none
    _end_job("idle")


def _job_tick():
    try:
        return _job_step()
    except Exception as ex:  # never leave the panel stuck on a job nobody is watching
        proc = _job.get("proc")
        if proc is not None and proc.poll() is None:
            proc.terminate()
        _end_job("failed", why="%s: %s" % (type(ex).__name__, ex))
        redraw_all()
        return None


def _read_lines():
    """Takes in what export.py has printed so far."""
    while True:
        try:
            line = _job["lines"].get_nowait()
        except queue.Empty:
            return
        _job["tail"] = (_job["tail"] + [line])[-20:]
        if line.startswith("PROGRESS ") and "/" in line:
            done, total = line[9:].split("/")
            _job.update(done=int(done), total=int(total))
        elif line.startswith("DONE "):
            _job["result"] = line[5:].rsplit(" ", 1)[0]
        elif line.startswith("FAILED "):
            _job["why"] = line[7:]


def _job_step():
    proc = _job.get("proc")
    if proc is None:
        return None
    _read_lines()
    redraw_all()
    if proc.poll() is None:
        return 0.5
    if _job["reader"].is_alive() or not _job["lines"].empty():
        return 0.1  # its last lines are still coming
    tail = next((l for l in reversed(_job["tail"]) if l.strip()), "")
    if _job["state"] == "exporting":
        if proc.returncode == 0 and _job["result"]:
            _end_job("done")
        else:
            if _job["total"] and _job["done"] < _job["total"]:
                _remove_partial()  # export.py cleans up after itself unless it crashed; a finished one is kept
            _end_job("failed", why=_job["why"] or tail)
    redraw_all()
    return None


def _time_left():
    done, total, started = _job["done"], _job["total"], _job["started"]
    if not done or not started or done >= total:
        return None
    left = round((time.time() - started) / done * (total - done))
    return divmod(left, 60)


# --- operators ------------------------------------------------------------------------------

def _tip(key):
    return classmethod(lambda cls, context, properties: text(context.scene, key))


class STUDIO_OT_guard(bpy.types.Operator):
    """Swallows a gesture or key in the studio layout; passes it on everywhere else"""
    bl_idname = "studio.guard"
    bl_label = "Studio guard"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return {"FINISHED"} if in_studio(context) else {"PASS_THROUGH"}


class STUDIO_OT_layout(bpy.types.Operator):
    bl_idname = "studio.layout"
    bl_label = "Switch layout"
    bl_options = {"INTERNAL"}
    full: bpy.props.BoolProperty()

    @classmethod
    def description(cls, context, properties):
        return text(context.scene, "tip_full" if properties.full else "tip_back")

    def execute(self, context):
        if self.full:
            leave_studio()
        else:
            enter_studio()
        return {"FINISHED"}


class STUDIO_OT_fit(bpy.types.Operator):
    bl_idname = "studio.fit"
    bl_label = "Whole frame"
    bl_options = {"INTERNAL"}
    description = _tip("tip_fit")

    def execute(self, context):
        fit_camera()
        return {"FINISHED"}


class STUDIO_OT_more(bpy.types.Operator):
    # A button, not a layout panel: a layout panel cannot sit inside the group's box. Open or
    # closed is kept only till a file opens, so it marks nothing unsaved and leaves no undo step.
    bl_idname = "studio.more"
    bl_label = "More"
    bl_options = {"INTERNAL"}
    description = _tip("tip_more")
    group: bpy.props.StringProperty()

    def execute(self, context):
        _state["more"] ^= {self.group}
        redraw_all()
        return {"FINISHED"}


class STUDIO_OT_save(bpy.types.Operator):
    bl_idname = "studio.save"
    bl_label = "Save"
    bl_options = {"INTERNAL"}
    description = _tip("tip_save")

    def execute(self, context):
        bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")  # a file never saved asks where
        return {"FINISHED"}


class STUDIO_OT_save_look(bpy.types.Operator):
    bl_idname = "studio.save_look"
    bl_label = "Save look"
    bl_options = {"INTERNAL"}
    description = _tip("tip_save_look")
    name: bpy.props.StringProperty()

    @staticmethod
    def free_name(scene):
        taken, n = set(saved_looks()[0]), 1
        while text(scene, "version", n=n) in taken:
            n += 1
        return text(scene, "version", n=n)

    def invoke(self, context, event):
        if not looks_dir():
            self.report({"ERROR"}, text(context.scene, "need_save"))
            return {"CANCELLED"}
        self.name = self.free_name(context.scene)
        return context.window_manager.invoke_props_dialog(
            self, title=text(context.scene, "save_look"), confirm_text=text(context.scene, "ok_save"))

    def draw(self, context):
        self.layout.prop(self, "name", text=text(context.scene, "name"))

    def execute(self, context):
        name = re.sub(r'[\\/:*?"<>|]', "-", self.name).strip().lstrip(".")  # what no system allows in a file name
        write_look(context.scene, name or self.free_name(context.scene))
        redraw_all()
        return {"FINISHED"}


class STUDIO_OT_load_look(bpy.types.Operator):
    bl_idname = "studio.load_look"
    bl_label = "Load look"
    bl_options = {"UNDO", "INTERNAL"}
    description = _tip("tip_load")
    name: bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        if not os.path.exists(look_path(self.name)):
            return {"CANCELLED"}
        with open(look_path(self.name), encoding="utf-8") as fh:
            data = json.load(fh)  # read first: loading Previous swaps it with what is on screen
        write_look(scene, PREVIOUS)
        apply_look(scene, data)
        touch(scene)
        return {"FINISHED"}


class STUDIO_OT_delete_look(bpy.types.Operator):
    bl_idname = "studio.delete_look"
    bl_label = "Delete look"
    bl_options = {"INTERNAL"}
    description = _tip("tip_delete")
    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event, title=text(context.scene, "delete", name=self.name),
            confirm_text=text(context.scene, "ok_delete"))

    def execute(self, context):
        if os.path.exists(look_path(self.name)):
            os.remove(look_path(self.name))
        _state["looks"] = None
        redraw_all()
        return {"FINISHED"}


class STUDIO_OT_export_pick(bpy.types.Operator):
    bl_idname = "studio.export_pick"
    bl_label = "Pick"
    bl_options = {"INTERNAL"}  # a choice for this session: no undo step, nothing unsaved
    what: bpy.props.StringProperty()
    value: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        prefix = {"format": "tip_f_", "quality": "tip_q_"}.get(properties.what)
        return text(context.scene, prefix + properties.value) if prefix else ""

    def execute(self, context):
        _pick[self.what] = self.value
        redraw_all()
        return {"FINISHED"}


class STUDIO_OT_export(bpy.types.Operator):
    bl_idname = "studio.export"
    bl_label = "Export"
    bl_options = {"INTERNAL"}
    description = _tip("tip_export")

    def execute(self, context):
        if _job["state"] == "exporting":
            return {"CANCELLED"}
        if not bpy.data.filepath:
            self.report({"ERROR"}, text(context.scene, "need_save"))
            return {"CANCELLED"}
        why = start_export(context.scene)
        if why:
            self.report({"ERROR"}, text(context.scene, "failed", why=why))
            return {"CANCELLED"}
        return {"FINISHED"}


class STUDIO_OT_export_cancel(bpy.types.Operator):
    bl_idname = "studio.export_cancel"
    bl_label = "Cancel export"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        cancel_export()
        redraw_all()
        return {"FINISHED"}


class STUDIO_OT_open_exports(bpy.types.Operator):
    bl_idname = "studio.open_exports"
    bl_label = "Show in folder"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        result = _job.get("result") or ""
        bpy.ops.wm.path_open(filepath=result if os.path.isdir(result) else os.path.dirname(result))
        return {"FINISHED"}


# --- the panel ------------------------------------------------------------------------------

def _panel_id(name):
    return "studio_%08x" % zlib.crc32(name.encode("utf-8"))


def _choices(layout, t, label, what, values, prefix, current):
    row = layout.split(factor=0.25)
    row.label(text=label)
    buttons = row.row(align=True)
    for value in values:
        op = buttons.operator("studio.export_pick", text=t(prefix + value), depress=value == current)
        op.what, op.value = what, value


def draw_export(layout, scene, t):
    busy = _job["state"] == "exporting"
    col = layout.column()
    col.enabled = not busy
    formats = FORMATS_STILL if is_still(scene) else FORMATS
    grid = col.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    for f in formats:
        op = grid.operator("studio.export_pick", text=t("f_" + f), depress=f == picked_format(scene))
        op.what, op.value = "format", f
    _choices(col, t, t("size"), "size", SIZES, "s_", _pick["size"])
    _choices(col, t, t("quality"), "quality", QUALITIES, "q_", _pick["quality"])
    col.label(text="%d × %d" % export_size(scene))

    state = _job["state"]
    if state == "exporting":
        done, total = _job["done"], _job["total"]
        if done:
            left = _time_left()
            msg = t("exporting", done=done, total=total)
            if left:
                msg += t("left_min", m=left[0], s=left[1]) if left[0] else t("left_s", s=left[1])
        else:
            msg = t("preparing")
        layout.progress(factor=done / total if total else 0.0, type="BAR", text=msg)
        layout.label(text=t("slower"))
        layout.operator("studio.export_cancel", text=t("cancel"), icon="CANCEL")
    else:
        go = layout.row()
        go.scale_y = 1.4
        go.operator("studio.export", text=t("export_go"), icon="RENDER_ANIMATION")
        layout.label(text=t("snapshot"))
        if state == "done":
            box = layout.box()
            box.label(text=t("done"), icon="CHECKMARK")
            box.label(text=os.path.basename(_job["result"]))
            box.operator("studio.open_exports", text=t("open_folder"), icon="FILE_FOLDER")
        elif state == "failed":
            box = layout.box()
            box.alert = True
            box.label(text=t("failed", why=_job["why"]), icon="ERROR")


def draw_controls(col, scene, keys):
    for key, label in keys:
        path = '["%s"]' % key
        ui = _ui_data(scene, key)
        items = ui.get("items")
        if items or ui.get("subtype") in ("COLOR", "COLOR_GAMMA"):
            # Name on the left, as Blender lays these out; a short choice shows every option as a
            # button.
            row = col.split(factor=0.4)
            row.label(text=label)
            if items and len(items) <= 3:
                row.row(align=True).prop(scene, path, expand=True)
            else:
                row.prop(scene, path, text="")
        else:
            col.prop(scene, path, text=label, slider=True)


class STUDIO_PT_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY
    bl_label = "Studio"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return is_piece(context.scene)

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        t = functools.partial(text, scene)

        row = layout.row(align=True)
        save = row.row(align=True)
        save.alert = save.enabled = bpy.data.is_dirty
        save.operator("studio.save", text=t("save") if bpy.data.is_dirty else t("saved"), icon="FILE_TICK")
        row.operator("studio.fit", text=t("fit"), icon="ZOOM_ALL")

        if scene.frame_end > scene.frame_start and hasattr(context.window_manager, "studio_time"):
            header, body = layout.panel("studio_time")
            header.label(text=t("time"))
            if body:
                r = body.box().row(align=True)
                playing = context.screen.is_animation_playing
                r.operator("screen.animation_play", text="", icon="PAUSE" if playing else "PLAY")
                r.prop(context.window_manager, "studio_time", text="", slider=True)
                r.label(text=t("of_seconds", total="%g" % round(_state["duration"] or 0, 1)))

        for group, shown, more, post in control_groups(scene):
            header, body = layout.panel(_panel_id(group), default_closed=post)
            header.label(text=group)
            if body:
                box = body.box()
                if shown:  # an empty column still takes a row's height
                    draw_controls(box.column(), scene, shown)
                if more:
                    is_open = group in _state["more"]
                    row = box.row()
                    row.alignment = "LEFT"
                    row.operator("studio.more", text=t("more", n=len(more)), emboss=False,
                                 icon="DISCLOSURE_TRI_DOWN" if is_open else "DISCLOSURE_TRI_RIGHT").group = group
                    if is_open:
                        row = box.row()
                        row.separator(factor=1.5)
                        draw_controls(row.column(), scene, more)

        header, body = layout.panel("studio_looks")
        header.label(text=t("looks"))
        if body:
            body.operator("studio.save_look", text=t("save_look"), icon="ADD")
            names, has_previous = saved_looks()
            if has_previous:
                body.operator("studio.load_look", text=t("previous"), icon="LOOP_BACK").name = PREVIOUS
            for name in names:
                r = body.row(align=True)
                r.operator("studio.load_look", text=name).name = name
                r.operator("studio.delete_look", text="", icon="X").name = name

        header, body = layout.panel("studio_export")
        header.label(text=t("export"))
        if body:
            draw_export(body, scene, t)

        layout.separator(type="LINE")
        full = in_studio(context)
        layout.operator("studio.layout", text=t("full") if full else t("back"),
                        icon="FULLSCREEN_EXIT" if full else "FULLSCREEN_ENTER").full = full


# --- keeping the studio layout safe ---------------------------------------------------------

# (keymap, space, key, value, modifiers). Orbiting, view and shading pies, wireframe, x-ray,
# overlays, gizmos, walk, hiding, the sidebar and toolbar, maximize, and I / Ctrl+D over a control:
# a keyframed or driven look value no longer follows their drag. Ctrl+Option+Space stays open:
# it is how a Blender user leaves, and the timer notices.
GUARDED = [
    ("3D View", "VIEW_3D", "TRACKPADPAN", "ANY", {}),
    ("3D View", "VIEW_3D", "MOUSEROTATE", "ANY", {}),
    ("3D View", "VIEW_3D", "MIDDLEMOUSE", "PRESS", {}),
    ("3D View", "VIEW_3D", "Z", "PRESS", {}),
    ("3D View", "VIEW_3D", "Z", "PRESS", {"shift": True}),
    ("3D View", "VIEW_3D", "Z", "PRESS", {"alt": True}),
    ("3D View", "VIEW_3D", "Z", "PRESS", {"shift": True, "alt": True}),
    ("3D View", "VIEW_3D", "ACCENT_GRAVE", "PRESS", {}),
    ("3D View", "VIEW_3D", "ACCENT_GRAVE", "PRESS", {"shift": True}),
    ("3D View", "VIEW_3D", "ACCENT_GRAVE", "PRESS", {"ctrl": True}),
    ("3D View Generic", "VIEW_3D", "N", "PRESS", {}),
    ("3D View Generic", "VIEW_3D", "T", "PRESS", {}),
    ("Object Mode", "EMPTY", "H", "PRESS", {}),
    ("Object Mode", "EMPTY", "H", "PRESS", {"shift": True}),
    ("Screen", "EMPTY", "SPACE", "PRESS", {"ctrl": True}),
    ("User Interface", "EMPTY", "I", "PRESS", {}),
    ("User Interface", "EMPTY", "D", "PRESS", {"ctrl": True}),
]
_keymaps = []


def _after_load():
    if is_piece(bpy.context.scene):
        ensure_time_prop(bpy.context.scene)
        enter_studio()
    return None


@persistent
def _on_load(_):
    _state.update(studio=False, looks=None, fit=None, more=set())
    if not bpy.app.background:
        bpy.app.timers.register(_after_load, first_interval=0.3)


@persistent
def _on_save(_):
    redraw_all()  # the save button changes


classes = (STUDIO_OT_guard, STUDIO_OT_layout, STUDIO_OT_fit, STUDIO_OT_more, STUDIO_OT_save,
           STUDIO_OT_save_look, STUDIO_OT_load_look, STUDIO_OT_delete_look, STUDIO_OT_export_pick, STUDIO_OT_export,
           STUDIO_OT_export_cancel, STUDIO_OT_open_exports, STUDIO_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for km_name, space, key, value, mods in GUARDED:
            km = kc.keymaps.new(name=km_name, space_type=space)
            _keymaps.append((km, km.keymap_items.new("studio.guard", key, value, **mods)))
    bpy.app.handlers.load_post.append(_on_load)
    bpy.app.handlers.save_post.append(_on_save)
    if not bpy.app.background:  # enabled while a piece is already open
        bpy.app.timers.register(_after_load, first_interval=0.3)


def unregister():
    if _state["studio"] and not bpy.app.background:
        leave_studio()  # do not leave them in a stripped window with no panel to get out
    if _job["state"] != "idle":
        cancel_export()  # no headless Blender left rendering with nobody to report to
    for fn in (_tick, _after_load, _job_tick):
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
    for handlers, fn in ((bpy.app.handlers.load_post, _on_load), (bpy.app.handlers.save_post, _on_save)):
        if fn in handlers:
            handlers.remove(fn)
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    if hasattr(bpy.types.WindowManager, "studio_time"):
        del bpy.types.WindowManager.studio_time
    _state.update(studio=False, duration=None, looks=None, fit=None, more=set())
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
