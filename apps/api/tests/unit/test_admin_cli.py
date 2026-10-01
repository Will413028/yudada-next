import runpy
from pathlib import Path

import pytest


def test_invalid_admin_input_never_discloses_password(monkeypatch: pytest.MonkeyPatch) -> None:
    fields = iter(["test_admin", "測試管理者"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(fields))
    marker = "short_test"
    monkeypatch.setattr("getpass.getpass", lambda prompt: marker)
    script = Path(__file__).resolve().parents[2] / "scripts/create_admin.py"
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(script), run_name="__main__")
    assert marker not in str(caught.value)
    assert "Invalid account" in str(caught.value)
