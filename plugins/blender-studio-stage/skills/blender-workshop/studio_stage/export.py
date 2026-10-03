# Master: render what gets handed over, from a copy saved out of their open Blender.
#   blender -b --factory-startup -Y <copy.blend> --python-exit-code 1 --python export.py -- \
#       --out <path, no extension> [--format mp4] [--size full] [--quality final] [--frame N]
# format:  mp4 (plays anywhere) · prores (for editing) · png-sequence · frame (one frame as PNG)
#          · png / tiff / jpeg (a still piece, one frame long)
# size:    half · full · double, of the piece's own size
# quality: draft (half again, an eighth of the samples: to see the motion) · final (the file's own
#          settings, the ones tuned for delivery) · finer (twice the samples)
# --frame: for `frame`; defaults to the frame the file is on. A still piece renders its one frame.
# Never overwrites: an existing target is refused. Renders into <name>.part and renames it when
# complete, so a run that is killed leaves a .part, never a file that looks finished; while a .part
# of that name exists (a run under way, or one that was stopped) the name is refused. Prints
# PROGRESS <done>/<total> per frame, then DONE <path> <seconds>, or FAILED <why> with anything
# half-written removed. Nothing is saved.
# Verified on Blender 5.2.2 LTS (macOS).
import argparse, os, shutil, sys, time
import bpy

args = argparse.ArgumentParser(prog="export.py")
args.add_argument("--out", required=True)
args.add_argument("--format", default="mp4", choices=["mp4", "prores", "png-sequence", "frame", "png", "tiff", "jpeg"])
args.add_argument("--size", default="full", choices=["half", "full", "double"])
args.add_argument("--quality", default="final", choices=["draft", "final", "finer"])
args.add_argument("--frame", type=int)
opt = args.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

sc = bpy.context.scene
r = sc.render
ims = r.image_settings
VIDEO = opt.format in ("mp4", "prores")
STILL = opt.format in ("frame", "png", "tiff", "jpeg")
target = None  # what this run writes, the .part; removed again if it fails


def fail(why):
    try:
        if target and os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        elif target and os.path.isfile(target):
            os.remove(target)
    except OSError:
        pass  # a file held open elsewhere; saying why matters more
    print("FAILED " + " ".join(str(why).split()), flush=True)
    sys.exit(1)


if sc.camera is None:
    fail("The scene has no camera.")

# --- where it goes ----------------------------------------------------------------------------

ext = {"mp4": ".mp4", "prores": ".mov", "jpeg": ".jpg", "tiff": ".tif"}.get(opt.format, ".png")
path = opt.out if opt.format == "png-sequence" else opt.out + ext
if os.path.exists(path):
    print("FAILED %s already exists; choose another --out." % path, flush=True)
    sys.exit(1)
try:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
except OSError as ex:
    print("FAILED Cannot write there: %s" % ex, flush=True)
    sys.exit(1)
part = opt.out + ".part" + ("" if opt.format == "png-sequence" else ext)
try:  # claimed in one step: a .part already there may be a run still rendering
    os.mkdir(part) if opt.format == "png-sequence" else open(part, "x").close()
except FileExistsError:
    print("FAILED %s exists: an export of this name is running, or one was stopped; delete it or "
          "choose another --out." % part, flush=True)
    sys.exit(1)
target = part
r.use_file_extension, r.use_overwrite, r.use_placeholder = True, True, False
if opt.format == "png-sequence":  # a folder of numbered frames, named for the folder they end up in
    r.filepath = os.path.join(part, os.path.basename(opt.out) + "_####")
elif VIDEO:
    r.filepath = part  # without its extension, Blender would add the frame range to the name
else:
    r.filepath = opt.out + ".part"

# --- size and quality -------------------------------------------------------------------------

scale = {"half": 0.5, "full": 1.0, "double": 2.0}[opt.size] * (0.5 if opt.quality == "draft" else 1.0)
w = max(2, round(r.resolution_x * r.resolution_percentage / 100 * scale))
h = max(2, round(r.resolution_y * r.resolution_percentage / 100 * scale))
if VIDEO:  # video codecs want an even width and height
    w, h = w + w % 2, h + h % 2
r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100

def use_gpu():
    """Cycles on a GPU when there is one: the kind already chosen first, then any other (OptiX before
    CUDA). Returns what it will render on, in words."""
    cp = bpy.context.preferences.addons["cycles"].preferences
    order = ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI")
    have = [t[0] for t in cp.get_device_types(bpy.context) if t[0] != "NONE"]
    for kind in sorted(have, key=lambda k: (k != cp.compute_device_type, order.index(k) if k in order else 99)):
        devices = cp.get_devices_for_type(kind)
        gpus = [d for d in devices if d.type != "CPU"]
        if gpus:
            cp.compute_device_type = kind
            for d in devices:
                d.use = d.type != "CPU"
            sc.cycles.device = "GPU"
            return "%s (%s)" % (gpus[0].name, kind)
    sc.cycles.device = "CPU"
    return "the CPU"


if r.engine == "CYCLES":
    if opt.quality == "draft":
        sc.cycles.samples = max(16, sc.cycles.samples // 8)
        sc.cycles.use_denoising = True
    elif opt.quality == "finer":
        sc.cycles.samples *= 2
    print("DEVICE " + use_gpu(), flush=True)
elif hasattr(sc, "eevee"):
    if opt.quality == "draft":
        sc.eevee.taa_render_samples = max(8, sc.eevee.taa_render_samples // 8)
    elif opt.quality == "finer":
        sc.eevee.taa_render_samples *= 2

# --- format -----------------------------------------------------------------------------------

has_sound = (bool(sc.sequence_editor) and any(s.type == "SOUND" for s in sc.sequence_editor.strips_all)) or \
    any(ob.type == "SPEAKER" and ob.data.sound for ob in sc.objects)
if VIDEO:
    ims.media_type, ims.file_format, ims.color_mode = "VIDEO", "FFMPEG", "RGB"
    ff = r.ffmpeg
    if opt.format == "mp4":  # plain 8-bit H.264, the kind every player takes
        ff.format, ff.codec, ff.constant_rate_factor, ff.ffmpeg_preset = "MPEG4", "H264", "HIGH", "GOOD"
        ff.use_lossless_output, ims.color_depth = False, "8"
        ff.audio_codec = "AAC" if has_sound else "NONE"
    else:
        ff.format, ff.codec, ff.ffmpeg_prores_profile = "QUICKTIME", "PRORES", "422_HQ"
        ff.audio_codec = "PCM" if has_sound else "NONE"
else:
    ims.media_type = "IMAGE"
    if opt.format == "jpeg":
        ims.file_format, ims.color_mode, ims.quality = "JPEG", "RGB", 92
    elif opt.format == "tiff":
        ims.file_format, ims.color_mode, ims.color_depth, ims.tiff_codec = "TIFF", "RGB", "16", "DEFLATE"
    else:
        ims.file_format, ims.color_mode, ims.color_depth, ims.compression = \
            "PNG", "RGBA" if r.film_transparent else "RGB", "8", 15

# --- render -----------------------------------------------------------------------------------

frames = list(range(sc.frame_start, sc.frame_end + 1, sc.frame_step))
total = 1 if STILL else len(frames)
done = []


def after_frame(*_):
    done.append(1)
    print("PROGRESS %d/%d" % (len(done), total), flush=True)


bpy.app.handlers.render_post.append(after_frame)
print("PROGRESS 0/%d" % total, flush=True)
t0 = time.perf_counter()
try:
    if STILL:
        if opt.format == "frame":
            sc.frame_set(opt.frame if opt.frame is not None else sc.frame_current)
        else:
            sc.frame_set(sc.frame_start)  # a still piece is its first frame
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
except RuntimeError as ex:
    fail("Blender stopped rendering: %s" % ex)
secs = round(time.perf_counter() - t0, 1)

if len(done) != total:
    fail("Only %d of %d frames were rendered." % (len(done), total))
if opt.format == "png-sequence":
    name = os.path.basename(opt.out)
    missing = [f for f in frames if not os.path.isfile(os.path.join(part, "%s_%04d.png" % (name, f)))]
    if missing:
        fail("%d frames are missing from %s, the first %d." % (len(missing), opt.out, missing[0]))
elif not os.path.isfile(part) or os.path.getsize(part) == 0:
    fail("Rendering finished but %s is missing or empty." % path)
target = None  # finished: from here on a failure keeps the .part
if os.path.exists(path):
    fail("%s appeared while rendering; the render is kept as %s." % (path, part))
for attempt in range(5):  # on Windows a scanner may hold a just-written file for a moment
    try:
        os.replace(part, path)
        break
    except PermissionError:
        time.sleep(1)
    except OSError as ex:
        fail("Rendered, but could not name it %s (%s); the render is kept as %s." % (path, ex, part))
else:
    fail("Rendered, but could not name it %s; the render is kept as %s." % (path, part))
print("DONE %s %s" % (path, secs), flush=True)
