# WaveTone Harness Test Plan and Results

## Test Inventory Plan

- `test_core.py`: 12 unit tests for project manifests, audio probing, session logs,
  and backend discovery.
- `test_full_e2e.py`: 5 E2E tests covering CLI subprocess workflows and real
  WaveTone launch smoke coverage.

## Unit Test Plan

- Create a manifest from a supported WAV file.
- Reject missing files and unsupported extensions.
- Save and load schema-compatible JSON.
- Add labels in sorted time order.
- Set tempo and analysis options.
- Probe a generated WAV file with the Python stdlib.
- Fall back to stat metadata for malformed WAV files.
- Probe non-WAV audio with a single stable `ffprobe -show_entries` argument.
- Append and reload session events.
- Reject invalid session JSON schemas with clear `ValueError`s.
- Resolve `WAVETONE_EXE` from the environment.
- Preserve inherited project and JSON context for REPL-style nested CLI
  invocations.

## E2E Test Plan

### CLI Project Workflow

Simulates an agent preparing an audio file before opening it in WaveTone.

Operations:

1. Generate a real WAV fixture.
2. Run `cli-anything-wavetone --json project new`.
3. Run `project set-tempo`.
4. Run `project add-label`.
5. Run `audio probe`.

Verified:

- CLI JSON is parseable.
- Project file exists.
- Labels and tempo persist.
- Audio metadata is correct.

### CLI Backend Workflow

Simulates an agent validating the installed WaveTone backend.

Operations:

1. Run `wavetone doctor`.
2. Run `wavetone formats`.
3. Launch the real `wavetone.exe` with a generated WAV and terminate it after a
   short wait.

Verified:

- Doctor reports all bundled files.
- Formats include documented WaveTone audio extensions.
- Real WaveTone process starts and is terminated by the smoke test.

## Test Results

Command:

```bash
$env:PATH = "$env:APPDATA\Python\Python313\Scripts;$env:PATH"
python -m pytest cli_anything\wavetone\tests\ -v -s
```

Result:

```text
collected 17 items

cli_anything/wavetone/tests/test_core.py::test_create_project_manifest PASSED
cli_anything/wavetone/tests/test_core.py::test_rejects_unsupported_audio PASSED
cli_anything/wavetone/tests/test_core.py::test_save_load_project_roundtrip PASSED
cli_anything/wavetone/tests/test_core.py::test_labels_are_sorted PASSED
cli_anything/wavetone/tests/test_core.py::test_update_analysis_settings PASSED
cli_anything/wavetone/tests/test_core.py::test_probe_wav_metadata PASSED
cli_anything/wavetone/tests/test_core.py::test_probe_malformed_wav_falls_back_to_stat PASSED
cli_anything/wavetone/tests/test_core.py::test_ffprobe_uses_single_show_entries_argument PASSED
cli_anything/wavetone/tests/test_core.py::test_session_event_log PASSED
cli_anything/wavetone/tests/test_core.py::test_session_rejects_invalid_schema PASSED
cli_anything/wavetone/tests/test_core.py::test_find_wavetone_from_env PASSED
cli_anything/wavetone/tests/test_core.py::test_cli_preserves_inherited_project_and_json_context PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestCLISubprocess::test_project_audio_workflow_json PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestCLISubprocess::test_formats_json PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestRealWaveToneBackend::test_doctor_real_backend PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestRealWaveToneBackend::test_launch_real_backend_with_wav PASSED

17 passed in 3.43s
```

## Coverage Notes

- Unit tests cover manifest creation, validation, persistence, labels, tempo,
  analysis settings, audio probing, malformed WAV fallback, session logs,
  session schema validation, backend discovery, ffprobe argument construction,
  and inherited CLI project and JSON context.
- CLI subprocess tests resolve and use the installed `cli-anything-wavetone`
  entry point.
- Real backend coverage launches `C:\Users\Hp\Desktop\wavetone2.6.1\wavetone.exe`
  with a generated WAV and terminates it after a short wait.
- Real backend tests are skipped automatically when Windows or a ready WaveTone
  extraction is unavailable.
- WaveTone 2.61 has no documented headless analysis/export API. Export
  verification remains a known gap until a stable non-GUI automation surface is
  discovered.
