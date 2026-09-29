"""Общие фикстуры pytest. Корень проекта добавляется в sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config as cfg  # noqa: E402


@pytest.fixture(autouse=True)
def fake_client_secret(tmp_path, monkeypatch):
    """client_secret.json в тестах — временный файл, чтобы не трогать config/."""
    secret = tmp_path / "client_secret.json"
    secret.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cfg, "client_secret_path", lambda: secret)
    return secret


@pytest.fixture
def missing_client_secret(tmp_path, monkeypatch):
    """client_secret.json отсутствует (для теста NO_CLIENT_SECRET)."""
    missing = tmp_path / "nope" / "client_secret.json"
    monkeypatch.setattr(cfg, "client_secret_path", lambda: missing)
    return missing


def make_video_folder(base: Path, name: str = "video.mp4") -> Path:
    """Готовая валидная папка ролика."""
    folder = base / "video001"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"\x00" * 1024)
    (folder / "thumbnail.jpg").write_bytes(b"\xff\xd8" * 8)
    (folder / "title.txt").write_text("Шарль Бодлер — Сплин", encoding="utf-8")
    (folder / "description.txt").write_text(
        "Шарль Бодлер.\n\nСтихотворение «Сплин».", encoding="utf-8"
    )
    return folder