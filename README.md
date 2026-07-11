# Open Rails — Native Apple Silicon (macOS) Port

This is a **native macOS build of the [Open Rails](http://www.openrails.org/) train
simulator engine**, running directly on Apple Silicon (M-series) Macs — no Windows,
no Wine, no virtual machine.

As far as we can tell, this is the **first native Mac build of the Open Rails engine.**
It has been confirmed running successfully after a full set of cross-platform fixes.

> This repository is the complete Open Rails source (a fork of
> [`openrails/openrails`](https://github.com/openrails/openrails)) with the macOS port
> committed on top. To see exactly what changed, diff this branch against upstream
> `openrails/openrails` `master`.

---

## ✅ Status

- Runs natively on **Apple Silicon (arm64)** macOS.
- Uses the **.NET runtime** with **SDL2** and **OpenAL** (via Homebrew) for windowing,
  input and audio.
- Loads standard MSTS / Open Rails route and rolling-stock content, same as the
  Windows version.

---

## 🛠 Requirements

- A **Mac with Apple Silicon** (M1/M2/M3/M4…).
- **.NET runtime** installed (the build targets `net8.0` and runs on newer runtimes
  via `--roll-forward LatestMajor`).
- **Homebrew** with the native libraries:
  ```bash
  brew install sdl2 openal-soft dotnet
  ```
- MSTS / Open Rails **route + rolling-stock content** to actually drive a train
  (same content the Windows Open Rails uses).

---

## ▶️ Running

From the built program folder (`Program/`):

```bash
# Tell the loader where the Homebrew native libs are
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

# --roll-forward LatestMajor lets the net8.0 build run on a newer installed .NET runtime
dotnet exec --roll-forward LatestMajor RunActivity.dll [arguments...]
```

Example (explorer mode):

```bash
dotnet exec --roll-forward LatestMajor RunActivity.dll \
  -start "-explorer" "PATH_TO_ROUTE" "CONSIST" "PATH" "TIME" "SEASON" "WEATHER"
```

The command-line arguments are the same as Windows Open Rails.

---

## 🔧 What was changed for macOS

The port adds a small set of platform-compatibility shims and cross-platform fixes
across `Orts.Common`, `Orts.Content`, `Orts.Formats.*` and `RunActivity`. Key new
files:

| File | Purpose |
|------|---------|
| `Orts.Common/FileSystemCompat.cs` | Case-insensitive / cross-platform path handling |
| `Orts.Common/SimpleIniReader.cs` | Portable INI reading (no Windows API) |
| `Orts.Formats.Msts/DxtDecompress.cs` | Software DXT texture decompression |
| `RunActivity/Viewer3D/Popups/DpiCompat.cs` | DPI handling without Windows Forms |
| `RunActivity/Viewer3D/Popups/SkiaFont.cs` | Font rendering via SkiaSharp |
| `RunActivity/Viewer3D/UIThreadMarshal.cs` | Main-thread marshalling |
| `RunActivity/Viewer3D/UserInputRailDriverStub.cs` | RailDriver stub for non-Windows |

Plus numerous smaller edits to replace Windows-only APIs, fix path separators,
texture loading, and threading behaviour so the engine builds and runs on macOS.

---

## 🙏 Credits

- **Open Rails** and its engine — the [Open Rails team](http://www.openrails.org/)
  and all upstream contributors.
- **macOS / Apple Silicon port** — Aman.

## 📄 License

Open Rails is released under the **GNU General Public License (GPL)**. This port
inherits the same license — see [`LICENSE`](LICENSE).
