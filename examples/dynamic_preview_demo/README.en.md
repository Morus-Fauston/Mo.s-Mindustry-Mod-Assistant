# MoMA Dynamic Preview Demo

This directory is a runnable example project for MoMA's dynamic preview API.
It loads real JSON and PNG assets from the reference mods under `../../辅助项目/参考模组/` at runtime.

## Run on Windows

Double-click `run.bat`, or run this command from the repository root:

```powershell
.venv\Scripts\python.exe examples\dynamic_preview_demo\run_demo.py
```

The demo does not modify the reference mods. It creates a temporary MoMA-compatible project for the selected unit and deletes it when the window closes.

The current adapter supports standard JSON units with a same-named PNG under `sprites/units/`. It also copies same-named layer PNGs such as `-cell`, `-full`, `-leg`, `-base`, and `-treads` when present.
