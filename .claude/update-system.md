# Update System

Source + frozen self-update, mirrors YoutubeDownloader. Default auto-check is OFF.

## Flow
- `cleanup_old_updates()` at startup removes `*.old`, `_update_*.bat`, `*.py.old`, `*.py.backup`
- `_check_for_updates(silent)` — GitHub API, compares via `_version_newer`
- `_show_update_dialog()` — Update Now / Open Releases / Later
- `_apply_update(release_data)` — routes: frozen → `_apply_update_frozen`, source → inline
- `_apply_update_frozen` → platform-specific Win/Linux variant

## Frozen self-update (Win + Linux)
1. Download asset to `<exe>.new` (Win: `Autoclicker.exe.new`, Linux: `Autoclicker-Linux.new`)
2. Verify SHA-256 against release `SHA256SUMS` (mandatory — abort if missing)
3. Rename dance: `running` → `.old`, `.new` → `running`
4. User closes + reopens; `.old` cleaned on next startup

Windows fallback: if rename fails (file locked), write `_update_<tmp>.bat` that waits for PID exit then `move /y`.

## Integrity
- Source updates: git blob SHA-1 (GitHub Contents API) + SHA-256 (mandatory)
- Frozen updates: SHA-256 only (from release SHA256SUMS)
- Asset names: `Autoclicker.exe`, `Autoclicker-Linux`, `SHA256SUMS`
- Download URLs validated to start with `https://github.com/jj-repository/autoclicker/`

## GitHub
Repo: `jj-repository/autoclicker`. Max download 5MB (source only; frozen has no enforced cap beyond 1KB min).
