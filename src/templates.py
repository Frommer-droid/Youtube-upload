"""Редактируемые шаблоны названия и описания видео.

Название: пользователь вводит только название песни, из него собирается
итоговый заголовок. Описание собирается из нейтрального шаблона,
двух ссылок (Telegram и MAX), переводчика и текста, введённого пользователем.

Шаблоны редактируются пользователем во вкладках интерфейса и сохраняются
в каталоге данных конкретной установки. Изменения применимы
сразу и для последующих запусков.
"""

from __future__ import annotations

import json
import logging

from . import config

logger = logging.getLogger("youtube_uploader.templates")

TITLE_TEMPLATE = "{song}"

DESCRIPTION_BODY = (
    "Ссылка Telegram: "
    "{telegram_url}\n"
    "Ссылка MAX: "
    "{max_url}\n"
    "Перевод: {translator}\n"
)

TITLE_PLACEHOLDER = "{song}"
DESCRIPTION_PLACEHOLDERS = ("{telegram_url}", "{max_url}")

TEMPLATE_KEYS = ("title", "description")

TITLE_VAR_MSG = (
    "В шаблоне названия нет переменной {{song}}.\n"
    "Добавьте её, иначе название песни не подставится."
)
DESCRIPTION_VAR_MSG = (
    "В шаблоне описания нет переменных {telegram_url} и/или {max_url}.\n"
    "Добавьте их, иначе ссылки не подставятся."
)


def templates_path() -> object:
    """Путь к templates.json в каталоге данных приложения."""
    return config.app_data_dir() / "templates.json"


def default_templates() -> dict[str, str]:
    """Стандартные шаблоны (используются при первом запуске)."""
    return {"title": TITLE_TEMPLATE, "description": DESCRIPTION_BODY}


def load_templates() -> dict[str, str]:
    """Шаблоны пользователя; повреждённые/отсутствующие заменяются стандартными."""
    result = default_templates()
    path = config.app_data_dir() / "templates.json"
    if not path.is_file():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Не удалось прочитать templates.json: %s", exc)
        return result
    if not isinstance(data, dict):
        return result
    for key in TEMPLATE_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value
    return result


def save_templates(data: dict[str, str]) -> None:
    """Сохранить шаблоны в каталог данных приложения."""
    path = config.app_data_dir() / "templates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {key: data.get(key, "") for key in TEMPLATE_KEYS}
    path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_title(song_name: str, template: str | None = None) -> str:
    """Итоговое название из названия песни и шаблона."""
    song = song_name.strip()
    tpl = template if template is not None else TITLE_TEMPLATE
    if TITLE_PLACEHOLDER not in tpl:
        raise ValueError(TITLE_VAR_MSG)
    return tpl.format(song=song)


def build_description(
    telegram_url: str = "",
    max_url: str = "",
    poem_text: str = "",
    template: str | None = None,
    translator: str = "",
) -> str:
    """Описание: шаблон + ссылки + переводчик + текст стихотворения.

    Пустые ссылки оставляют пустую строку после подписи, текст стихотворения
    при отсутствии пропускается; перед стихом всегда ровно одна пустая строка.
    """
    body = template if template is not None else DESCRIPTION_BODY
    for placeholder in DESCRIPTION_PLACEHOLDERS:
        if placeholder not in body:
            raise ValueError(DESCRIPTION_VAR_MSG)
    translator_value = translator.strip()
    if not translator_value and body == DESCRIPTION_BODY:
        body = body.replace("Перевод: {translator}\n", "")
    body = body.format(
        telegram_url=telegram_url.strip(),
        max_url=max_url.strip(),
        translator=translator_value,
    )
    poem = poem_text.strip()
    if poem:
        separator = "\n" if body.endswith("\n") else "\n\n"
        return body + separator + poem + "\n"
    return body
