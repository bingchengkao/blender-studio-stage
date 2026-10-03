# Setting up for Blender work

Read this when a machine or a piece is being set up for the Blender workshop, or when the
self-check says something is missing. Do only what is missing.

## What the machine needs

| What | Why | Roughly |
|---|---|---|
| Blender, a version both add-ons below accept (their manifests' `blender_version_min`; 5.2 today) | everything | 330 MB download, about 1 GB on disk |
| git | fetches the channel's server from its official repository | on a Mac, Apple's command line tools: several hundred MB behind a system dialog |
| uv | runs the channel's server, and fetches a Python 3.10 or newer for it | a few MB; Python 25 MB download, 66 MB on disk |
| The channel's server, fetched the first time a piece uses its version | the channel's half outside Blender | about 20 MB download, about 225 MB in uv's cache |
| The official MCP add-on, from the Blender Lab extension repository `https://lab.blender.org/` | the channel's half inside Blender | 18 KB |
| The `studio_stage` add-on beside this file | the panel and the studio layout | under 100 KB |
| Online Access on, in Blender's preferences | the MCP add-on opens no connection without it, and Blender cannot reach its repository | — |

Look at what is already there, versions included, before listing anything. On a Mac, `git`
exists even when it does not, and running it pops the install dialog: ask `xcode-select -p`
instead. Tell them in one message what is missing and how big it is, ask once, and on a yes
install all of it. Use the usual way of their system — Mac, Windows or Linux — and Blender's own
download page for Blender.

**Their Blender is too old**: ask whether they still use it for other work. If not, upgrade it.
If they do, install the new one beside it and leave theirs alone; then settle which Blender opens
a `.blend` when they double-click one, or they land in the old one with no panel and no channel.
Blender keeps add-ons and preferences per version, so a new version gets them again.

Blender's command line installs the add-ons (`blender -c extension --help`): add the Blender Lab
repository and install the MCP add-on from it, enabled; build `studio_stage/` into a package
(`extension build`, output outside this folder) and install that file. Online Access is a
preference: turn it on from Blender's Python and save the preferences. Until it is on, the
repository commands need `--online-mode`. The MCP add-on decides at start-up, so ask them to save
and close any Blender they have open; it takes the setting when it opens again.

The official server lives at `https://projects.blender.org/lab/blender_mcp`, in `mcp/`. The PyPI
package named `blender-mcp` is somebody else's project. The repository's archive downloads refuse
uv; git works.

## What each piece gets

A piece keeps one version of the channel's server from start to delivery, all its parts
included: the official newest the day it starts. A later piece gets a later one. Pinned to a
commit, it starts in under a second and needs no network once fetched.

1. Read the commit at the head of the official repository (`git ls-remote <repo> HEAD`).
2. In the piece's folder, write `.mcp.json`. Absolute paths: an app may not see the shell's PATH.
   ```json
   {"mcpServers": {"blender": {
     "command": "<uvx>",
     "args": ["--python", ">=3.10", "--from", "git+<repo>.git@<commit>#subdirectory=mcp", "blender-mcp"],
     "env": {"BLENDER_PATH": "<this Blender's executable>"}}}}
   ```
   Claude Code finds it from any folder below.
3. In each folder a conversation on this piece will open in — the piece's, each part's — merge
   `"enabledMcpjsonServers": ["blender"]` into `.claude/settings.local.json`. Claude Code takes
   this permission only from the folder the conversation opened in; without it the first
   conversation asks, with "continue without" chosen in advance.
4. Run the self-check on the piece's .blend — at the start, its copy of `starter.blend` — with
   `-- --open`, telling them a Blender window will appear. Its first run fetches the server.
   If the newest server and the released add-on do not get along, pin the commit the add-on's
   release was tagged from instead.
5. The workshop's note survives plugin updates by naming things for what they are: it opens by
   telling whoever works on the piece to load this plugin's skill, `blender-studio-stage:blender-workshop`,
   before any Blender work, and it calls the plugin's folder its `installPath` in
   `~/.claude/plugins/installed_plugins.json` — never a path, which changes with every update.
6. A conversation has only the channel it started with, so the work goes on in a new one.

The add-on inside Blender belongs to the machine, not the piece. When a new piece starts, offer
to update it (`blender --online-mode -c extension update`); that changes it for pieces under way too.
