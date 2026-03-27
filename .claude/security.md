# Security & Thread Safety

## Download Security
- MAX_DOWNLOAD_SIZE: 5MB limit
- SHA256 verification required, aborts if missing/mismatch
- `.py.backup` before replace

## Thread Safety
- Clicker state: `clicker1_lock`, `clicker2_lock`
- Hotkey timing dict: lock-protected
- UI from threads: `window.after()` (pynput) / `_safe_after()` (evdev, crash-safe)
- Hotkey capture state: lock-protected (evdev)

## Review (2026-03-15 — Production Ready)
Path traversal protection, interval validation, no secrets, 5MB download limit, SHA256, backup ✓
Clicker/hotkey/hotkey-timing locks, safe UI callbacks, hotkey capture lock ✓
37/37 tests, no unused imports, consistent error handling, logging ✓
