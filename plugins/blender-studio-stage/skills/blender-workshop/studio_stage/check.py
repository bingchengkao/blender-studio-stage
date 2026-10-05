# Defect check, for the model: what the picture on their screen cannot show, mostly what a change
# made through the channel can break. It renders nothing; Blender's renderer is not what breaks.
#   blender -b --factory-startup -Y <copy.blend> --python-exit-code 1 --python check.py
# Run it on a copy saved from their open Blender, as delivery would see it: no add-ons, no scripts.
# One PROBLEM line each, then RESULT; exit 1 when anything is found.
# Not covered: geometry-node simulation zones left unbaked (5.2 offers no baked flag to read), and
# physics baked to a disk cache beside the .blend, which a copy saved elsewhere renders frozen.
# Verified on Blender 5.2.2 LTS.
import os, sys
import bpy

sc = bpy.context.scene
found = []


def problem(text):
    if text not in found:  # one line per problem, however many channels or curves share it
        found.append(text)
        print("PROBLEM " + text, flush=True)


controls = (sc["studio"].to_dict() if "studio" in sc else {}).get("controls", {})

# A control whose look value is gone: the panel drops it without a word.
for key, c in controls.items():
    if key not in sc:
        problem("The control '%s' points at look value %s, which no longer exists." % (c.get("label", key), key))


def actions(ad):
    """The action playing on this data, and those in its NLA strips."""
    if ad.action:
        yield ad.action
    for track in ad.nla_tracks:
        for strip in track.strips:
            if strip.action:
                yield strip.action


# A broken driver leaves its property at the last value it computed: the picture looks right and the
# control does nothing. One that needs Python stops the same way in a Blender that runs no scripts.
sc.frame_set(sc.frame_start)  # drivers say whether they are valid once evaluated
seen = set()
for idb in bpy.data.all_ids:
    for owner in (idb, getattr(idb, "node_tree", None)):  # material, world and light trees are embedded
        ad = getattr(owner, "animation_data", None) if owner is not None else None
        if ad is None or owner.session_uid in seen:
            continue
        seen.add(owner.session_uid)
        where = "%s %s%s" % (type(idb).__name__, idb.name, "" if owner is idb else " (its node tree)")
        for fc in ad.drivers:
            if owner == sc and fc.data_path.startswith('["look_'):  # the add-on blocks Ctrl+D, not every way in
                problem("Look value %s has a driver: its control no longer follows their drag." % fc.data_path[2:-2])
            d = fc.driver
            if d.type == "SCRIPTED" and not d.is_simple_expression:
                problem("Driver on %s %s needs Python (`%s`): it stops in their Blender, which runs no scripts."
                        % (where, fc.data_path, d.expression))
            elif not d.is_valid or fc.mute:
                problem("Driver on %s %s is broken (%s)." % (where, fc.data_path,
                        "muted" if fc.mute else "points at something gone or an expression that fails"))
        # A keyframed look value snaps back whenever time moves, undoing their drag.
        if owner == sc:
            for action in actions(ad):
                for layer in action.layers:
                    for strip in layer.strips:
                        for bag in strip.channelbags:
                            for fc in bag.fcurves:
                                if fc.data_path.startswith('["look_'):
                                    problem("Look value %s is keyframed: it snaps back when time moves."
                                            % fc.data_path[2:-2])

# Post their view shows but the master would not.
if sc.compositing_node_group is not None and not sc.render.use_compositing:
    problem("Compositing is off for renders: the master would come out without post.")

for path in bpy.utils.blend_paths(absolute=True, packed=False, local=False):
    if not path:  # physics on a disk cache in its default folder reports an empty path
        continue
    probe = os.path.dirname(path) if ("#" in path or "<" in path) else path  # sequences and tiles: their folder
    if not os.path.exists(probe):
        problem("Missing file: %s" % path)

# Unbaked physics is worked out frame by frame from the start: a frame rendered on its own, as you
# render one to look at it, shows it wrong. The master, rendered in order, is not affected.
caches = []
rbw = sc.rigidbody_world
if rbw and rbw.enabled and rbw.collection and len(rbw.collection.objects):
    caches.append(("rigid bodies", rbw.point_cache))
for ob in sc.objects:
    for mod in ob.modifiers:
        if mod.type in ("CLOTH", "SOFT_BODY") and mod.show_render:
            caches.append((ob.name, mod.point_cache))
    for ps in ob.particle_systems:
        if ps.settings.type == "EMITTER":
            caches.append((ob.name, ps.point_cache))
for name, cache in caches:
    if not cache.is_baked:
        problem("Physics on %s is not baked: a frame rendered on its own shows it wrong." % name)

print("RESULT " + ("ok" if not found else "%d problem%s" % (len(found), "" if len(found) == 1 else "s")), flush=True)
sys.exit(1 if found else 0)
