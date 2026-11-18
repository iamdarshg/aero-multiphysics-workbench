# TOOLCHAIN MANIFEST — Engineering Program v2

Host: Windows 11 (win32 x64), PowerShell 7 (`pwsh`).
Recorded: 2026-11-11T23:15 IST by DSH Lead (surplus/deepseek-v4.1-flash-1017).

## Detected tools

| Tool | Version / path | Status |
|---|---|---|
| git | 2.44.0.windows.1 | OK |
| gh | 2.96.0, authenticated as `iamdarshg` (scopes: gist, read:org, repo) | OK |
| python | 3.12.2 | OK |
| torch | 2.9.1+cu130, CUDA available | OK |
| numpy / scipy | 2.2.6 / 1.16.3 | OK |
| pytest | 8.3.5 (pytest-timeout NOT installed) | OK |
| mypy | 1.15.0 | OK |
| kicad-cli | `C:\Program Files\KiCad\9.0\bin\kicad-cli.exe` | OK |
| docker | 29.8.2 (Docker Desktop; engine currently stopped) | OK |
| wsl | present; only `docker-desktop` distro registered (no Ubuntu) | PARTIAL |
| cmake | `C:\Program Files\CMake\bin\cmake.exe` | OK |
| ninja | `%APPDATA%\Python\Python312\Scripts\ninja.exe` | OK |
| g++ | `C:\Users\Darsh Gupta\gcc\bin\g++.exe` | OK |
| gmsh | `%APPDATA%\Python\Python312\Scripts\gmsh.bat` | OK |
| iverilog | `C:\Users\Darsh Gupta\bin\iverilog.exe` | OK |
| verilator | MISSING | BLOCKED (CS-G7 partial) |
| ccx (CalculiX) | `D:\mcp\eng\freecad\FreeCAD_1.1.4-Windows-x86_64-py311\bin\ccx.exe` | OK |
| opencode | v2.0.32, default `surplus/deepseek-v4.1-flash-1017` | OK |
| claude | present (`claude.ps1`) | OK (other swarm) |
| codex | present (`codex.ps1`) | OK |

## Not available (fail closed, do not fabricate)

- OpenFOAM native: not installed. Container path available via Docker
  (`opencfd/openfoam-default:2406`) once the engine is started.
- preCICE: not installed.
- openEMS / CSXCAD / HFSS / FEKO: not installed.
- VNA / physical bench: not available.
- TeX distro: not installed; portable Tectonic at `tools/tectonic`.

## Notes

- `git config --global core.longpaths true` was set because `drone-mech` contains
  paths > 260 chars; the first clone failed checkout until this was enabled.
- `pytest-timeout` is absent, so `--timeout=` is not a valid pytest argument here.
- mypy on `aero-multiphysics-workbench` fails at config level
  ("Source file found twice under different module names") before type checking;
  this is a path/module-mapping defect, not 505 type errors. Re-derive with
  `--explicit-package-bases` or a scoped target before quoting any mypy number.
