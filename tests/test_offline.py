"""Guard rails for the offline promise and the bundled font."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_IMPORTS = (
    "socket",
    "urllib",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "websockets",
    "ftplib",
    "smtplib",
    "telnetlib",
)


def source_files():
    for path in (ROOT / "game").rglob("*.py"):
        yield path
    yield ROOT / "main.py"


def test_no_network_imports_in_game_code():
    pattern = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_.]+)", re.MULTILINE)
    offenders = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            module = match.group(1)
            if any(module == bad or module.startswith(bad + ".") for bad in FORBIDDEN_IMPORTS):
                offenders.append(f"{path.name}: {module}")
    assert offenders == [], f"network imports found: {offenders}"


def test_no_network_urls_in_game_code():
    pattern = re.compile(r"https?://")
    offenders = []
    for path in source_files():
        if "http" in path.read_text(encoding="utf-8"):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line) and not line.strip().startswith("#"):
                    offenders.append(f"{path.name}:{line_no}: {line.strip()}")
    assert offenders == [], f"network URLs found: {offenders}"


def test_bundled_font_exists_and_is_truetype():
    font = ROOT / "assets" / "fonts" / "CEFFontsCJK-Regular.ttf"
    assert font.exists()
    assert font.stat().st_size > 1_000_000
    assert font.read_bytes()[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")


def test_ofl_license_present():
    text = (ROOT / "assets" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in text
    assert "Version 1.1" in text


def test_gitignore_covers_environment_and_artifacts():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".venv/", "__pycache__/", "*.pyc", "build/", "dist/", "*.egg-info/"):
        assert pattern in text
