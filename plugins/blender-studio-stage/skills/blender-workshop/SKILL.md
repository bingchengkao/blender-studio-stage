---
name: blender-workshop
description: The studio's workshop in Blender, for pieces whose light must behave like real light (glass, a perfume bottle). Use when standing one up, or for any work in a workshop that holds a .blend.
---

# Blender workshop

Some pieces need light that behaves like light: a glass bead that bends the table behind it and
focuses a bright spot into its own shadow, a perfume bottle holding a softbox in its shoulder.
Those are made in Blender. It already has the timeline, two renderers, video output and a
compositor; what it lacks is the studio's way of working, and that is what this carries.

The person you make it for may never have opened Blender, whose window looks like a cockpit.
They watch the piece in their own Blender while you change it.

## Everything here moves

Blender, the channel to it and you will all be newer next year, so this page says what must be
true, not which setting does it.

- **Your memory of Blender's names may be from an older Blender.** A setting, operator or Python
  name you have not just seen work here, check against this Blender. The documentation the
  channel carries is one Blender version's and may be older than theirs; this Blender's own
  Python, which can list what exists, has the last word. When a call fails, look it up rather
  than guess again.
- **Nobody on a piece finds the same thing out twice.** A name that worked, a trap, a setting
  that fixed something: write it into the workshop's note as you learn it — with parts, into the
  piece's note, which every part reads.
- **A one-minute self-check comes before a piece's first work**:
  `blender -b <piece.blend> --python-exit-code 1 --python selfcheck.py`, the script beside this
  file. It reaches their Blender through the channel, renders a frame, moves a look value,
  watches the picture change and puts it back, and says which step failed and the likely why.
  When no Blender answers it stops; `-- --open` makes it open the piece itself, for when they
  have no Blender open — tell them a window will appear. Tell them the outcome in plain words and
  keep its RECORD line — versions, graphics card, seconds per frame — in that note. No RESULT
  line means the check itself broke; if it says it is out of date, do its steps by hand through
  the channel. A later conversation reads the note instead: one call through the channel shows
  the versions, and the check runs again only when one differs or something misbehaves.

## The channel to the open Blender

Today it is an MCP server. Whatever its tools are called, it lets you run Python in the Blender
they have open, see its window, read its documentation and list missing files. Use what it offers.
Each piece pins the channel's server in its own folder, the official newest the day it started,
and keeps it to delivery; the add-on inside Blender belongs to the machine. Setting up a machine
or a piece — what to install, how big, how a piece gets its channel — is in `setup.md` beside
this file.

- **While they have the file open, change it only through the channel.** Write the file on disk
  behind them and their next save throws away your change, or yours throws away their tuning.
  With no channel, ask them to close the file first; they see your change when they reopen it.
- **Headless Blender reads the file on disk, which lags their window.** Before a headless frame,
  check or master, save a copy from their open Blender through the channel and work from that.
  Their own file stays untouched.
- **A value set from Python neither redraws nor marks the file unsaved.** The next screenshot shows
  the old picture, the panel still says saved, and they can close Blender without being asked.
  After a change, tag the scene for an update, redraw, and push an undo step — which also lets
  them undo you.
- **In the studio layout nothing stays selected**: a click there selects nothing, and what your code
  leaves selected or active is cleared a moment later, so a stray key cannot move it. Within one
  call your selection holds; across calls, reach objects by name.
- **Keep a way back.** Before code that could leave their scene half-changed, push an undo step;
  if it fails partway, push another and undo once, and their scene is as it was — values, objects
  and materials alike. Never reopen or swap the file they have open: reopening drops what they
  have not saved, swapping sends their next save somewhere else.
- **One Blender on the channel at a time.** Before you change anything, check which file it has
  open — with parts, it may be another part's. Headless renders of several parts can still run
  side by side.

## The six roles

| Role | In Blender |
|---|---|
| Frame | Built in: render frame N headless from that saved copy; the same every time (Cycles too, its seed fixed by default). Or see their window through the channel. |
| Look values | Plain custom properties on the scene, driving materials, lights and objects. |
| Panel | The `studio_stage` add-on beside this file, installed into Blender once: the Studio panel lists the look values the control mode calls for. |
| Saved looks | The same panel: named sets of look values in `looks/` beside the .blend. |
| Master | `studio_stage/export.py` beside this file, headless from that saved copy; the panel's Export runs the same. |
| Defect check | `studio_stage/check.py`, the same way. Yours: the panel does not run it. |

**A piece starts as a copy of `starter.blend`**, beside this file. It holds what every piece
shares and nothing it looks like: the post set, render settings, and the layout. Lights, camera,
backdrop and objects are the piece's own. The layout is why a copy and not a script: the sidebar
opens on the Studio tab only because the file says so, and code cannot switch a live tab.

**Look values live in one place**: plain custom properties on the scene named `look_…` (saved looks
gather them by that prefix), never ones an add-on defines, so a headless render or the check reads
them with no add-on loaded. Each is a number, a colour (three floats, colour subtype), a choice (an
integer with items) or an on/off; range, items and a one-line hint go in its UI data. Set one only
with a value of its own kind: a float into a choice, or 1 into an on/off, quietly makes it a plain
number and its control a slider.

Drivers carry the values into materials, lights and objects. Blender does not run a file's Python
by default, so a driver that needs Python silently stops in their Blender. Keep expressions to what
it evaluates without Python — in 5.2 arithmetic, comparisons, `a if c else b`, `frame`, and
functions such as min, max, clamp, smoothstep, radians — and check that each driver you write
qualifies; Blender reports it.

**Look values are never keyframed**: a keyframed one snaps back whenever time moves, undoing their
drag. What changes over time reads them through a driver on `frame`. A timing control (when the
light swells, how fast the bottle turns) is a look value in seconds or per second, counted as the
panel's time slider counts, from the first frame. Sliders show no unit; put it in the hint.

A look value gets a control only when `scene["studio"]["controls"]` lists it, with `label`, `group`
and `rank`; one not listed is a value without a control. Rank is the lowest control mode that shows
it, 1 being what matters most; rank 0 is post, shown in every mode, folded, after the rest. Groups
and controls appear in the order listed. `mode` is the control mode from the workshop's note;
`lang` names their language. Labels, group names and hints are what they read: the starter's post
set is English, so translate all three when you set the piece up. The panel's own buttons come in
`en` and `zh-Hant`; for another language put its words in `studio["ui"]`, keyed as in the add-on's
`STRINGS`.

**Dragging must show the result at once.** In EEVEE that is about 0.2 s to a clean picture. When it
stops keeping up with their hand, lower the live view's quality yourself — never the file's render
settings — unless an export is running, which slows the view by itself.

## Rendering

**One renderer per piece: what they tune is what gets delivered.** EEVEE by default; it keeps up
with their hand. Cycles only when EEVEE cannot draw what the brief needs — usually light focused
through glass (caustics). Switching is a fork in how it is made, so put it to them first. On the
M5 MacBook Pro we measured, a drag cleared in 2–8 s in Cycles, a 5-second film took 20–30 minutes
against five, and the first Cycles render on a machine waited about 40 s more while
the graphics card was prepared. Nothing in the studio layout says a picture is still rendering, so
before one that will take more than a few seconds, tell them to wait before judging.

**Quality is yours to get right.** Final quality is whatever the file's render settings are, so
tune them early: render a frame at those settings and full size, and the one after it to see
flicker; look for noise, jagged edges and flicker, look up which setting in this Blender governs
each, change it, render again, and time it on this machine. While making, ask now and then whether
the quality is enough or worth more time. **Before the first final-quality master — yours, or theirs
from the panel, so before you first point them at Export — always settle it with them**: show the
frame, give seconds per frame and the whole film's time, and say what would make it better and how
much longer that would cost.

**EEVEE approximates what it cannot trace**: look at a frame of anything inside or behind glass. In
5.2, liquid inside refracting glass came out invisible or black; glass faked as see-through
(blended, casting no shadow) showed it. If the fake loses what the brief needs, that is the case
for Cycles.

**Post is Blender's compositor.** The starter carries a full post set, exposure to grain, as look
values like the rest, at rank 0.

## Master, stills, check

Both are scripts in `studio_stage/` beside this file, run headless on a copy saved from their open
Blender, the way delivery sees the piece — no add-ons, no scripts:
`blender -b --factory-startup -Y <copy.blend> --python-exit-code 1 --python <script> [-- options]`.

- **The defect check, `check.py`, finds what the picture cannot show**, mostly what a change through
  the channel breaks: a driver broken or needing Python (the picture keeps its last value, the
  control goes dead), a control whose look value is gone (it drops off the panel), a keyframed look
  value, post off for renders, a missing file, physics not baked (a frame you render on its own to
  look at shows it wrong). It renders nothing and takes about a second. Run it after work that
  touched look values, controls, drivers or files, before you hand the piece back, and before any
  final-quality master — before you point them at Export too, since the panel does not stop on it.
- **The master, `export.py`**: format, size and quality, as its header lists. The panel's Export
  runs it with the same words: draft is half size with an eighth of the samples, to see the motion;
  final is the file's own settings; finer doubles the samples. Point `--out` into `exports/` beside
  *their* .blend, named as the panel names exports: `<piece>_<MMDD-HHMM>`, `_draft` for drafts. It
  never overwrites, and removes what it half-wrote when it fails; one killed outright leaves
  `<name>.part…`, unfinished, and while that is there — as it is while an export runs — the name is
  refused.
- **A render longer than a few minutes — a whole-film draft, a master — runs in a process of its
  own that outlives this conversation**, writing its progress to a file beside the output, so a
  later conversation finds it too. Watch that file while the conversation lasts, so you know when
  it ends; tell them where it will land and when, and to leave the computer awake till then. Or
  point them to the panel's Export, which their Blender runs for as long as it stays open.
- **A still is a piece one frame long**: the same scene, delivered as a print-size image — set the
  file's own size to the print size, since the panel's sizes are halves and doubles of it. Blender
  sets type poorly; type on a poster is laid out elsewhere — say so when the brief has much of it.

## Walking them through Blender

**Start in the conversation, and assume they have never used Blender.** Be concrete: which part of
the window is which, what to drag, what they will see when they do — "the column on the right
holds the controls; drag 'glass haze' to the right and the bead's reflections go soft."

What they see: a piece opens with nothing but the picture and the panel. The view cannot be turned
or clicked into, only zoomed (pinch or scroll), and a button puts the whole frame back. The save
button lights up while anything is unsaved; the bottom button opens full Blender and comes back.
A colour shows as a swatch, a short choice as a row of buttons, an on/off as a checkbox. Export, at
the bottom, has buttons for format, size and quality; pressing it renders what is on screen at that
moment into `exports/` while they keep tuning, the picture slower meanwhile. Moving a thing by hand
is full Blender's. Call the buttons by the words the panel shows them.

**If they say they are lost, look at their window** through the channel and talk about what is on
it. Only if that is not enough, put a note inside Blender.

In full Blender, a picture that suddenly looks wrong is most likely a stray key: H hides what is
selected, Z changes how the view is drawn. The studio layout blocks those.

What each control is for, the studio introduces; this only says where it sits in Blender.

## Not this workshop's

Web pages, front-ends, logos and stylised 3D belong to another workshop. To share the piece, send
the .blend with what it reads from outside packed in — saved from full Blender, or it opens with no
menus for someone without the add-on.

---
Measured on Blender 5.2.2 LTS, the official MCP add-on 1.0.3 and its server at main@dbbf836, on
one M5 MacBook Pro.
