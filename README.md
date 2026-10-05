# blender-studio-stage

A Claude Code plugin that makes Blender a workshop for the `studio` plugin: where a piece is built,
tuned by the person it is for, and handed over from.

**Which pieces**: those whose look comes from how light falls — glass that bends what is behind
it, liquid that glows through it, soft shadows from a window; product ads for perfume, glass,
jewellery. A stylised look can be one too, when it is drawn from the light, such as halftone dots
that grow where the light falls. Web pages and front-ends belong to the web template; for other
stylised work, weigh what the light adds against the cost. The cost is theirs: Blender on their
machine, and Blender's window in front of them.

## The six roles

| Role | Here | How |
|---|---|---|
| Frame | yes, built in | Blender renders frame N headless, the same every time (Cycles too: its seed is fixed by default). |
| Look values | yes | Custom properties `look_…` on the scene, driving materials, lights and objects; readable with no add-on loaded. |
| Panel | yes | The Studio panel in Blender lists the controls; drag one and the picture follows — on an M5 MacBook Pro, about 0.2 s in EEVEE, 2–8 s to clear in Cycles. |
| Saved looks | yes | The same panel saves named sets of look values to `looks/` beside the .blend and brings them back. |
| Master | yes | `export.py`, one command: MP4, ProRes, PNG sequence or a still, at draft, final or finer quality. The panel's Export runs the same. |
| Defect check | yes, for Claude | `check.py`, one command, about a second: broken drivers, missing files, look values keyframed or driven, post switched off, physics not baked (geometry-node simulations and disk caches excepted) — what the picture cannot show. The panel does not run it. |

What it cannot do:
- Renders take time: on an M5 MacBook Pro a 5-second 1080p film took about 5 minutes in EEVEE and
  20–60 in Cycles.
- Measured on one Mac only. Windows and Linux are untested.
- Long or finely set type is laid out elsewhere; a title or a short line is set in the scene.
- One Blender at a time can be changed live; renders of several can run side by side.
- No shareable page of the panel: someone without Claude gets the `.blend` and tunes it in full
  Blender, without the Studio panel. What is delivered is the master.

## Install

```bash
claude plugin marketplace add bingchengkao/blender-studio-stage
claude plugin install blender-studio-stage@blender-studio-stage
```

The machine also needs Blender, git, uv, two Blender add-ons and one Blender preference. On a Mac
with none of it: about 400 MB to download and 1.3 GB on disk, plus several hundred MB of Apple's
command line tools for git.

**After installing**, in the same conversation: read `skills/blender-workshop/setup.md` in the
plugin's folder — its `installPath` in `~/.claude/plugins/installed_plugins.json` — and do what it
says: what the machine is missing (asked once, with sizes), the piece's channel to Blender, its
starting file, and a one-minute self-check that opens Blender, reaches it, renders a frame and moves
a value. The self-check passing is the workshop running; keep its RECORD line in the workshop's
note. The plugin and the channel reach only conversations that start afterwards, so the piece is
made in a new one, opened in the piece's folder.

## Verified on

Blender 5.2.2 LTS, the official Blender MCP add-on 1.0.3 and its server at `main@dbbf836`, macOS on
an M5 MacBook Pro.
