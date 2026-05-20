import json
import os
import subprocess
from pathlib import Path

from cli_anything.joplin.utils.joplin_backend import BackendConfig, find_joplin, run_joplin_command, run_joplin_json


def _npm_global_root() -> Path | None:
    """Best-effort lookup of npm's global ``node_modules`` directory.

    Returns ``None`` if npm is missing, fails, or produces no output. Errors
    here must never propagate to the caller -- this is only the last-resort
    leg of the ``backend version`` fallback path.
    """
    try:
        proc = subprocess.run(
            ["npm", "root", "-g"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    return Path(out) if out else None


def _joplin_package_json_candidates(binary_path: str) -> list[Path]:
    """Plausible ``package.json`` locations for the installed Joplin CLI.

    Handles the common npm/pnpm layouts:

    * Windows npm shim / custom prefix:
      ``<prefix>/joplin.cmd`` next to ``<prefix>/node_modules/joplin/package.json``.
    * Unix npm global default (and Homebrew / nvm symlinks):
      ``<prefix>/bin/joplin`` is a symlink into
      ``<prefix>/lib/node_modules/joplin/main.js``; resolving the symlink and
      taking the parent yields the package root.
    * Last resort: ``npm root -g`` to discover wherever npm actually keeps the
      global ``node_modules`` tree on this machine.
    """
    binary = Path(binary_path)
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        try:
            key = os.path.normcase(os.path.normpath(str(p)))
        except Exception:
            key = str(p)
        if key in seen:
            return
        seen.add(key)
        candidates.append(p)

    try:
        resolved = Path(os.path.realpath(binary))
    except OSError:
        resolved = binary

    # Symlinked binary points directly into the package (e.g. main.js at the
    # package root, or one level deep under bin/).
    add(resolved.parent / "package.json")
    add(resolved.parent.parent / "package.json")

    # Windows / custom-prefix layouts: shim next to a local node_modules tree.
    add(binary.parent / "node_modules" / "joplin" / "package.json")

    # Unix npm global default: <prefix>/bin/joplin -> <prefix>/lib/node_modules/joplin.
    add(binary.parent.parent / "lib" / "node_modules" / "joplin" / "package.json")

    npm_root = _npm_global_root()
    if npm_root is not None:
        add(npm_root / "joplin" / "package.json")

    return candidates


def _load_joplin_package_metadata(binary_path: str) -> dict | None:
    """Return the parsed Joplin ``package.json`` if any candidate matches.

    Only files whose ``"name"`` field is exactly ``"joplin"`` are accepted,
    so an unrelated neighbour ``package.json`` (e.g. another tool sharing the
    npm prefix) cannot impersonate the metadata.
    """
    for candidate in _joplin_package_json_candidates(binary_path):
        try:
            if not candidate.is_file():
                continue
            metadata = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(metadata, dict) and metadata.get("name") == "joplin":
            return metadata
    return None


def version_info(config: BackendConfig) -> dict:
    try:
        return run_joplin_command(["version"], config)
    except RuntimeError as exc:
        # Joplin 3.6.2's installed `command-version.js` may require
        # `../package.json`, which is missing in npm -g layouts. Fall back to
        # the package metadata next to the installed CLI -- searching every
        # known npm/pnpm global layout so the recovery actually fires on the
        # most common installs (Windows shim, Unix `/usr/local/bin -> lib/...`
        # symlink, Homebrew, nvm, custom prefix).
        if "package.json" not in str(exc):
            raise

        binary = find_joplin(config.binary)
        metadata = _load_joplin_package_metadata(binary)
        if metadata is None:
            raise
        return {
            "command": [str(binary), "version"],
            "returncode": 0,
            "stdout": metadata.get("version", ""),
            "stderr": f"Fallback after broken Joplin version command: {exc}",
            "metadata": {
                "name": metadata.get("name"),
                "version": metadata.get("version"),
                "description": metadata.get("description"),
            },
        }


def dump_database(config: BackendConfig) -> dict:
    return run_joplin_json(["dump"], config, timeout=600)


def keymap(config: BackendConfig) -> dict:
    return run_joplin_command(["keymap"], config)


def geoloc(config: BackendConfig, note_ref: str) -> dict:
    return run_joplin_command(["geoloc", note_ref], config)


def export_sync_status(config: BackendConfig) -> dict:
    return run_joplin_command(["export-sync-status"], config, timeout=300)


def server_status(config: BackendConfig) -> dict:
    return run_joplin_command(["server", "status"], config)


def server_start(config: BackendConfig, exit_early: bool = True, quiet: bool = False) -> dict:
    args = ["server", "start"]
    if exit_early:
        args.append("--exit-early")
    if quiet:
        args.append("--quiet")
    return run_joplin_command(args, config, timeout=300)


def server_stop(config: BackendConfig) -> dict:
    return run_joplin_command(["server", "stop"], config)


def e2ee_status(config: BackendConfig) -> dict:
    return run_joplin_command(["e2ee", "status"], config)


def e2ee_target_status(config: BackendConfig, target_path: str, verbose: bool = False) -> dict:
    args = ["e2ee", "target-status", target_path]
    if verbose:
        args.append("--verbose")
    return run_joplin_command(args, config, timeout=300)


def e2ee_decrypt(
    config: BackendConfig,
    encrypted_text: str | None = None,
    retry_failed_items: bool = False,
    force: bool = False,
) -> dict:
    args = ["e2ee", "decrypt"]
    if encrypted_text:
        args.append(encrypted_text)
    if retry_failed_items:
        args.append("--retry-failed-items")
    if force:
        args.append("--force")
    return run_joplin_command(args, config, timeout=600)


def e2ee_decrypt_file(config: BackendConfig, file_path: str, output_dir: str | None = None) -> dict:
    args = ["e2ee", "decrypt-file", file_path]
    if output_dir:
        args += ["--output", output_dir]
    return run_joplin_command(args, config, timeout=600)
