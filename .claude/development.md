# Development

## Run
```bash
python autoclicker.py                   # pynput (Windows/macOS/Linux X11)
sudo python autoclicker_evdev.py        # evdev (Linux Wayland/games)
python -m pytest test_autoclicker.py -v
python -m pytest test_autoclicker.py --tb=short
```

## Tests (37 total)
- `TestValidateInterval` (9) — interval edge cases
- `TestKeyMapping` (7) — tkinter→evdev conversion
- `TestKeySerialization` (7) — key save/load
- `TestKeyDisplayName` (4) — human-readable names
- `TestConfigPersistence` (2) — config file handling
- `TestConstants` (2) — module constants
- `TestVersionComparison` (6) — semantic + pre-release

Mock evdev/pynput for platform-independent tests; `unittest.mock.patch` for file ops; `tempfile` for config.

## Dependencies
**pynput version:** tkinter (stdlib), pynput
**evdev version:** tkinter (stdlib), evdev, pynput.keyboard (key constants only)
