# Decisions & Standards

## Design Decisions
| Decision | Rationale |
|----------|-----------|
| Two separate files | Different backends; simpler than runtime switching |
| Root for evdev | uinput requires privileges; udev rules add setup complexity |
| Left-click only | Simplicity; right-click adds UI complexity for minimal benefit |
| 200ms hotkey cooldown | Prevents accidental double-toggles; tested value |
| Config in ~/.config/ | XDG standard; cross-platform |

## Won't Fix
| Issue | Reason |
|-------|--------|
| evdev requires sudo | By design; udev rules optional for users |
| No per-clicker button selection | Low demand, adds complexity |
| No click patterns | Feature creep; keep simple |
| pynput in some games | Use evdev; documented in README |

## Known Issues
1. evdev requires root — could use udev rules
2. No per-clicker mouse button selection
3. No mouse button support for keyboard presser

## Recent Fixes (Jan 2026)
`_safe_after()` for evdev crash-safe callbacks, `KeyCode.from_char()` exception handling, hotkey timing lock, empty checksum validation ✓

## Quality Standards
Target: personal utility — functional, secure, maintainable.
Do not optimize: click timing is as precise as Python/tkinter allows.

Version bumps default to **+0.0.1** unless told otherwise.
