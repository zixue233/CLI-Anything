---
name: "cli-anything-joplin"
description: "Command-line interface for Joplin workflows using the real joplin terminal backend"
---

# cli-anything-joplin

Use this skill to automate Joplin notebook, note, to-do, tag, attachment,
search, sync, and import/export workflows through a stateful harness backed by
the real `joplin` terminal binary.

## Requirements

- Python 3.10+
- Joplin terminal binary available as `joplin` (`npm install -g joplin`)
- Optional: pass `--profile` to target a specific Joplin profile

## Install

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=joplin/agent-harness
```

## Usage

```bash
# REPL mode (default)
cli-anything-joplin

# Machine-readable one-shot command
cli-anything-joplin --json notebooks list

# Stateful project
cli-anything-joplin project new --name demo -o ./demo.joplin-harness.json
cli-anything-joplin --project ./demo.joplin-harness.json notes create "Meeting note"

# Dry-run (no auto-save)
cli-anything-joplin --json --dry-run --project ./demo.joplin-harness.json notes create temp
```

## JSON output contract

When `--json` is enabled, commands return:

- `ok`: boolean
- `command`: stable command identifier such as `notes.list`, `todos.toggle`
- `data`: command payload
- `error`: null on success, or `{ type, message }` on failure

## Command groups

- `project`: `new`, `open`, `save`, `info`, `json`, `status`
- `notebooks`: `list`, `create`, `use`, `remove`
- `notes`: `list`, `create`, `set`, `get`, `remove`, `copy`, `move`, `rename`
- `todos`: `list`, `create`, `toggle`, `clear`, `done`, `undone`
- `tags`: `list`, `add`, `remove`, `notetags`, `tagnotes`
- `search`: `run`
- `sync`: `run` (`--target`, `--upgrade`, `--use-lock`)
- `interop`: `import`, `export`
- `config`: `get`, `set`, `list`, `export`, `import-file`
- `attach`: `add`
- `status`: `show`, `restore`
- `backend`: `version`, `dump`, `keymap`, `geoloc`, `export-sync-status`
- `server`: `status`, `start`, `stop`
- `e2ee`: `status`, `target-status`, `decrypt`, `decrypt-file`
- `session`: `status`, `undo`, `redo`, `history`

## Agent guidance

- Prefer `--json` for parseable output.
- Use `--project` when running multi-step workflows so history is persisted.
- One-shot mutating commands auto-save the project unless `--dry-run` is set.
- REPL mode does not auto-save; run `project save` explicitly.
- Some Joplin CLI builds gate `search` behind GUI mode; if you see
  `"only available in GUI mode"`, treat search as best-effort and parse the
  `error.message` in the JSON envelope to decide whether to retry inside the
  REPL.
- Joplin 3.6.x can have a broken `version` command in npm global layouts; the
  harness falls back to installed package metadata for `backend version`,
  probing the symlink-resolved binary directory, the Windows-style sibling
  `node_modules/joplin`, the Unix-style parent `lib/node_modules/joplin`, and
  finally `npm root -g`.

## Recommended workflow

1. `project new --name my-task -o ./my-task.joplin-harness.json` to create
   harness state.
2. Configure backend with `--profile /path/to/joplin-profile` to isolate from
   the user's personal Joplin install.
3. Run mutating commands with `--json --project ./my-task.joplin-harness.json`.
4. Use `session history` for a structured audit of what the agent did.
5. Export with `interop export <path> --format jex` for portable backups.

Current validation baseline (Windows + Joplin CLI 3.6.2):

- `python -m pytest -q cli_anything/joplin/tests/test_core.py` → `79 passed, 1 skipped`
- `python -m pytest -q cli_anything/joplin/tests` → `106 passed, 2 skipped`
