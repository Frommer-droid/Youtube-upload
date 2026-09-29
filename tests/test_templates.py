"""Тесты редактируемых шаблонов названия и описания."""

from __future__ import annotations

import pytest

from src import templates


def test_build_title_basic():
    assert templates.build_title("Моя песня") == "Моя песня"


def test_build_title_strips_whitespace():
    assert templates.build_title("  Моя песня \n") == "Моя песня"


def test_build_description_full():
    telegram = "https://example.com/telegram"
    max_url = "https://example.com/max"
    poem = "Первая строка\nВторая строка"
    result = templates.build_description(telegram, max_url, poem)
    expected = (
        f"Ссылка Telegram: {telegram}\n"
        f"Ссылка MAX: {max_url}\n"
        "\n"
        f"{poem}\n"
    )
    assert result == expected


def test_build_description_without_poem():
    result = templates.build_description("https://t.me/x", "https://max.ru/y", "")
    assert result == "Ссылка Telegram: https://t.me/x\nСсылка MAX: https://max.ru/y\n"


def test_build_description_empty_links():
    result = templates.build_description("", "", "Стих")
    assert "Ссылка Telegram: \n" in result
    assert "Ссылка MAX: \n" in result
    assert result.endswith("Стих\n")


def test_build_description_has_no_owner_specific_content():
    result = templates.build_description()
    assert result == "Ссылка Telegram: \nСсылка MAX: \n"


# --- пользовательские шаблоны (вкладки интерфейса) ---


def test_build_title_custom_template():
    result = templates.build_title("Моя песня", "Новый выпуск — «{song}»")
    assert result == "Новый выпуск — «Моя песня»"


def test_build_description_custom_template():
    result = templates.build_description(
        "tg", "mx", "Стих", "ТГ: {telegram_url}\nМАКС: {max_url}",
        translator="Не используется",
    )
    assert result == "ТГ: tg\nМАКС: mx\n\nСтих\n"


def test_build_description_substitutes_translator_in_custom_template():
    result = templates.build_description(
        "tg",
        "mx",
        "",
        "ТГ: {telegram_url}\nМАКС: {max_url}\nПеревод: {translator}",
        translator="  Иван Иванов  ",
    )
    assert result == "ТГ: tg\nМАКС: mx\nПеревод: Иван Иванов"


def test_default_description_exposes_translator_placeholder():
    assert "Перевод: {translator}" in templates.DESCRIPTION_BODY


def test_default_description_includes_nonempty_translator():
    result = templates.build_description("tg", "mx", translator="Иван Иванов")
    assert result == (
        "Ссылка Telegram: tg\n"
        "Ссылка MAX: mx\n"
        "Перевод: Иван Иванов\n"
    )


def test_build_title_missing_placeholder_raises():
    with pytest.raises(ValueError) as exc:
        templates.build_title("Сплин", "Без переменной")
    assert "{song}" in str(exc.value)


def test_build_description_missing_placeholder_raises():
    with pytest.raises(ValueError):
        templates.build_description("tg", "mx", "", "Только буквы")


def test_default_templates_are_valid():
    data = templates.default_templates()
    assert templates.TITLE_PLACEHOLDER in data["title"]
    assert all(p in data["description"] for p in templates.DESCRIPTION_PLACEHOLDERS)


def test_load_templates_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path))
    data = templates.load_templates()
    assert data == templates.default_templates()


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path))
    custom = {
        "title": "Моя серия: {song}",
        "description": "ТГ: {telegram_url}\nМАКС: {max_url}",
    }
    templates.save_templates(custom)
    loaded = templates.load_templates()
    assert loaded == custom
    assert (tmp_path / "templates.json").is_file()


def test_load_templates_merges_partial_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path))
    (tmp_path / "templates.json").write_text(
        '{"title": "Новый: {song}"}\n', encoding="utf-8"
    )
    data = templates.load_templates()
    assert data["title"] == "Новый: {song}"
    assert data["description"] == templates.DESCRIPTION_BODY


def test_load_templates_corrupt_file_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVATE_UPLOADER_DATA_DIR", str(tmp_path))
    (tmp_path / "templates.json").write_text("{broken", encoding="utf-8")
    assert templates.load_templates() == templates.default_templates()
