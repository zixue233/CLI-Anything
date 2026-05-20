# Test Plan — cli-anything-joplin

The suite has two files:

- `test_core.py` — pure unit + CLI-contract tests (no `joplin` binary required)
- `test_full_e2e.py` — CLI subprocess tests + real-backend workflows + full
  end-to-end roundtrip

Real-backend classes are skipped automatically when `joplin` is not on `PATH`.

## test_core.py (79 tests, 1 skipped on Windows)

Pure Python tests covering the harness surface. Safe to run anywhere without
a Joplin backend.

Coverage areas:

- Project schema, save/open roundtrip, unicode roundtrip, history shape
- Session lifecycle: set/get, snapshot, undo, redo, undo→redo chain,
  redo cleared on new snapshot, save/save-without-path, `mark_dirty`
- Session save regression: nested project path auto-creates missing parent
  directories before lock/write
- Backend runner: `find_joplin`, profile/no-profile invocation, error path,
  benign Node warning stripping, mixed warning+real-error handling, timeout,
  JSON parse fallback, empty stdout
- Core module argument shapes for: notes (cp/mv/ren/remove/get verbose),
  notebooks (rmbook flags), todos (mktodo/toggle/clear/done/undone), tags
  (tagnotes via `tag list`)
- JSON envelope shape (success + error)
- JSON contract per command group: notebooks, notes, todos, tags, search,
  sync, interop, config, session, attach, status, backend, server, e2ee
- Cross-group full workflow scripted against the mocked backend
- Error contract: search failure, missing note, missing backend, invalid
  export format
- `project status` and `project save` errors when no project is loaded
- Auto-save behavior: mutation auto-saves; `--dry-run` suppresses save
- Todo and notebook-remove flows write the expected history actions
- `session save` keeps undo/redo depth consistent across save → undo → redo → save
- Joplin source parity checks for `ls --format json`, `config --export`,
  `config --import-file`, `sync --upgrade/--use-lock`, `import --force`,
  `import --output-format`, `version`, `server`, and `e2ee` wrapper arguments
- Backend config precedence regression checks: CLI `--binary/--profile`
  overrides, project-persisted values when flags are omitted, and fallback to
  default `joplin`
- `backend version` fallback resolves the Joplin `package.json` across every
  common npm/pnpm layout: Windows shim + custom prefix
  (`<prefix>/joplin.cmd` + `<prefix>/node_modules/joplin`), Unix npm global
  symlink (`<prefix>/bin/joplin -> <prefix>/lib/node_modules/joplin/main.js`,
  skipped where symlinks need elevated privileges), Unix non-symlink wrapper
  (`<prefix>/bin/joplin` + `<prefix>/lib/node_modules/joplin`), `npm root -g`
  last-resort lookup, foreign `package.json` rejection (must have
  `"name": "joplin"`), and reraise-when-nothing-found / unrelated-error
  passthrough

```bash
python -m pytest -q cli_anything/joplin/tests/test_core.py
```

## test_full_e2e.py

### `TestCLISubprocess` (10 tests, backend-free)

Runs the CLI as a subprocess (either the installed console script or
`python -m cli_anything.joplin.joplin_cli`). Tests the externally visible
behavior:

- `--help` shows usage
- every command group (`project`, `notebooks`, `notes`, `todos`, `tags`,
    `search`, `sync`, `interop`, `config`, `attach`, `status`, `backend`,
    `server`, `e2ee`, `session`) accepts `--help`
- `project new`, `project info`, `project json`, `project save`,
  `project status` all return the expected JSON envelope
- `session status` reports `has_project=false` without a loaded project
- `--dry-run` does not mutate the project file
- unknown subcommand exits non-zero

### `TestBackendCommands` (6 tests, backend required)

Isolated real-backend command tests:

- project status/info while pointed at a real profile
- `notebooks list` and `notes list`
- `config get sync.target` and `config list`
- `status show`
- backend utilities (`backend version/dump`, `server status`, `e2ee status`)
- `session undo` / `session redo` return the documented errors on a clean
  project

### `TestBackendWorkflows` (11 tests, backend required)

Short backend flows:

- **Note lifecycle** — create notebook → use → create note → rename via `set`
  → get → remove note → remove notebook
- **Note organization** — copy, rename (via `ren`), move (via `mv`) between
  notebooks
- **Todo lifecycle** — create todo → list → done → undone → toggle → clear
- **Tagging** — add, list, notetags, tagnotes, remove
- **Search** — best-effort; tolerates the GUI-mode restriction by checking the
  error message when the backend rejects `search` outside the REPL
- **Sync (no target)** — verifies `sync run` returns a payload even when no
  target is configured
- **Export** — JEX and Markdown
- **Import** — Markdown directory import
- **Attach** — attach file to note, then read it back
- **Unicode** — skipped on Windows because `joplin.cmd` truncates non-ASCII
  args; the Python-only unicode roundtrip in `test_core.py` covers harness
  encoding
- **Session history persists** — verifies history actions land in the saved
  project file

### `TestBackendIntegration` (1 test, backend required)

Full end-to-end roundtrip used for agent demos and regression. Phases:

1. Inspect project (status / info / session)
2. Notebook setup (list, create main, create archive, use main)
3. Note lifecycle (list, create, rename via `set`, get, copy, create+move, rename via `ren`)
4. Todos (create, list, done, undone, toggle, clear)
5. Tags (add primary, add secondary, list, notetags, tagnotes, remove)
6. Attach (attach file, verbose get)
7. Status and config (status show, config get, config list)
8. Sync (no-op)
9. Export (JEX + MD)
10. Cleanup (remove notes, remove notebooks, save project, final status, session history)

After the run, the test verifies that the saved project's history contains
every expected action (`notebook.create`, `note.copy`, `note.move`,
`todo.toggle`, `tag.add`, `attach.add`, `interop.export`, …).

## Forcing the installed console script

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest -v -s cli_anything/joplin/tests/test_full_e2e.py
```

## Known limitations

- `joplin search` is gated to GUI mode on some Joplin CLI builds (3.x); the
  harness emits a normal `ok=false` JSON envelope with the original error
  message, and the workflow test accepts that shape.
- `joplin version` is broken in some npm global layouts because
  `command-version.js` requires `../package.json`. The harness falls back to
  the package metadata in any of: the symlink-resolved binary directory
  (Unix npm global / Homebrew / nvm), the sibling `node_modules/joplin`
  (Windows shim / custom prefix), the parent's `lib/node_modules/joplin`
  (non-symlinked `<prefix>/bin/joplin`), or whatever `npm root -g` reports.
  The original error is included in `stderr`.
- Non-ASCII process arguments on Windows pass through `joplin.cmd` →
  `cmd.exe`, which drops to the active code page. The unicode workflow test
  is therefore skipped on Windows. The Python-level unicode handling in the
  harness (project JSON, history, REPL) is covered in `test_core.py`.
