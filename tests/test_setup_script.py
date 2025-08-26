from pathlib import Path
import os
import stat


def test_setup_script_exists_and_executable():
    script = Path(__file__).resolve().parent.parent / "setup.sh"
    assert script.exists(), "setup.sh should exist at project root"
    mode = os.stat(script).st_mode
    assert mode & stat.S_IXUSR, "setup.sh should be executable"
    content = script.read_text(encoding="utf-8")
    assert "poetry install" in content
