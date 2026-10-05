"""Shared pytest fixtures.

Isolates editor state persistence: tests must never write to the real
app/config/editor_state.json (which stores the user's last opened project).
Instead, save/load are redirected to a per-test temp file.
"""

from __future__ import annotations

import json

import pytest

import app.core.session as session_mod


@pytest.fixture(autouse=True)
def isolate_preferences(tmp_path_factory, monkeypatch):
    """Keep runtime configuration private; legacy UI assertions use Chinese labels.

    Preference-specific tests may replace these paths with empty or real-default
    fixtures, so production defaults are still exercised explicitly.
    """
    from app.core import config_loader, settings
    from app.desktop import preferences

    # Keep configuration outside the fixture's project tree and extraction root.
    directory = tmp_path_factory.mktemp('isolated-user-config')
    settings_file = directory / 'settings.json'
    settings_file.write_text('{"display_name_mode":"zh"}', encoding='utf-8')
    monkeypatch.setattr(preferences, 'user_config_dir', lambda: directory)
    monkeypatch.setattr(settings, '_USER_FILE', settings_file)
    monkeypatch.setattr(settings, '_instance', None)
    monkeypatch.setattr(config_loader, '_current_mode', 'zh')


@pytest.fixture(autouse=True)
def isolate_editor_state(tmp_path, monkeypatch):
    """Redirect save/load_editor_state to a tmp file (session module scope)."""
    state_file = tmp_path / "editor_state.json"

    def fake_save(state: dict) -> None:
        state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def fake_load() -> dict:
        if not state_file.exists():
            return {}
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    # session.py imports these via `from .config_loader import ...`,
    # so patch the bound names in the session module itself.
    monkeypatch.setattr(session_mod, "save_editor_state", fake_save)
    monkeypatch.setattr(session_mod, "load_editor_state", fake_load)
