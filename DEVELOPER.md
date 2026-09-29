# YouTube Private Uploader — Developer Guide

Разработка, тестирование и сборка Python/PySide6-приложения для загрузки видео
на YouTube Data API v3 как Private.

## Окружение

- Python 3.12, проектный `.venv` в корне
- Все команды Python выполняются через `.\.venv\Scripts\python.exe`
- Зависимости: `requirements.txt` (runtime), `requirements-dev.txt` (pytest,
  PyInstaller, Pillow для генерации многоразмерной Windows-иконки)
- Рабочий OAuth-файл `config\client_secret.json` — в Git не попадает (.gitignore)

## Запуск

```powershell
.\.venv\Scripts\python.exe YouTubePrivateUploader.py
```

или как модуль: `.\.venv\Scripts\python.exe -m src.main`.

При первой загрузке открывается браузер Google для OAuth; токен сохраняется
в каталоге данных текущей установки.

## Архитектура

```text
src/
├── main.py              # QApplication, AppUserModelID, тема, показ окна, screen-hooks
├── gui.py               # MainWindow: 5 вкладок, worker-поток, плейлисты, форма, масштаб
├── theme.py             # стандартные токены One Dark и именованные оттенки
├── icons.py             # кэшируемые многоразмерные SVG-иконки вкладок и действий
├── styles.py            # One Dark QPalette/QSS + стабильное масштабирование шрифта
├── localization.py      # QTranslator + qtbase_ru.qm, русский locale
├── ui_scale.py          # чистые формулы масштаба (без Qt): auto/delta/final, clamp, migration
├── ui_scale_runtime.py  # одноразовый capture базовых размеров + пересчёт дерева виджетов
├── templates.py         # шаблоны названия/описания, templates.json, {song}/{telegram_url}/{max_url}/{translator}
├── youtube_auth.py      # OAuth 2.0, ensure_credentials, build_youtube, client_secret_exists
├── youtube_uploader.py  # run_upload: videos.insert (resumable), thumbnails.set,
│                        # list_playlists/add_video_to_playlist, retry/backoff, marker
├── folder_parser.py     # find_latest_video (по _ctime), универсальный find_cover
├── validators.py        # validate_package: имя песни, файлы, дубликат, шаблоны
├── models.py            # VideoPackage, UploadResult, ValidationIssue, UploadMarker
├── config.py            # пути (%APPDATA%), SCOPES (youtube.upload + force-ssl), лимиты
└── logging_setup.py     # логи в %APPDATA%\YouTubePrivateUploader\logs\
```

Правила:

- UI (`gui.py`) не содержит бизнес-логики — вызывает `core`-модули
- Долгие операции (OAuth, загрузка, плейлисты) выполняются в фоновом потоке
  с сигналами `WorkerSignals`; GUI-поток не блокируется
- До создания виджетов загружается русская локализация Qt
- Масштаб UI: модель `auto_percent + delta_percent -> final_percent -> scale_factor`,
  см. `ui_scale.py` и skill `pyside6-ui-scale-standard`; QSS, layout-метрики,
  размеры виджетов и иконок пересчитываются вместе, а screen/DPI-сигналы не
  форсируют resize окна
- Геометрия окна: `_normal_geometry` отдельно от maximized-состояния, кламп
  к рабочей области экрана при восстановлении, автосохранение в settings.json
  (debounce 400 мс), `_enforce_window_within_screens` как страховка. Формат v3
  хранит `window_pos_x`, `window_pos_y`, `window_width`, `window_height`,
  `maximized`; legacy-ключи v2 читаются и записываются для совместимости

## Настройки и runtime-состояние

`%APPDATA%\YouTubePrivateUploader\installations\<installation-id>\`:

- `settings.json` — геометрия окна, масштаб, плейлист, форма (`form`), рабочая папка
- `templates.json` — шаблоны названия/описания (создаются при первом запуске)
- `token.json` — OAuth-токен (не в Git)
- `logs\` — логи приложения

После загрузки следующего видео `_reset_for_new` сохраняет форму;
`_clear_song_translator_and_links` очищает только название песни, перевод и ссылки Telegram/MAX
и сразу сохраняет состояние. Поле «Перевод» хранится в `form.translator` и
подставляется в шаблон описания через необязательную переменную `{translator}`;
старые пользовательские шаблоны без неё продолжают работать.

Иконка приложения редактируется в `assets/app_icon.svg`. После изменения
перегенерировать Windows ICO командой:

```powershell
.\.venv\Scripts\python.exe .\Build_Tools\generate_app_icon.py
```

`logo.ico` содержит размеры 16/24/32/48/64/128/256 px. `src/main.py`
устанавливает её для `QApplication`, окна, панели задач и стандартных диалогов.

Стрелки выпадающих списков и кнопок меню — SVG в `assets/chevron-down*.svg`.
Они встроены через `assets/ui.qrc` в `src/ui_resources.py` и подключаются в теме.
После изменения SVG: `.\.venv\Scripts\pyside6-rcc.exe assets/ui.qrc -o src/ui_resources.py`.
Размер стрелок масштабируется в QSS; предусмотрены обычное, активное и отключённое состояния.

## Тесты

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

- YouTube API мокается, сеть в тестах не используется
- GUI-проверки темы, иконок, геометрии и maximized-состояния выполняются
  offscreen в `tests/test_gui_theme.py`

## Сборка

Установите `requirements-dev.txt` в проектное окружение и запускайте только
обёртку, которая формирует минимальный доверенный Windows `PATH`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

- `Build_Tools\YouTubePrivateUploader.spec` — канонический spec (в Git)
- `native_runtime.py` задаёт только выбранную `.venv`, PySide6, базовый Python,
  его DLL и Windows System32; `.spec` отклоняет чужие DLL до и после закрепления
  полной версии Qt MSVC runtime
- `audit_collect.py` проверяет происхождение всех бинарников и пять корневых
  MSVC DLL по `COLLECT-00.toc` до очистки рабочих файлов
- `post_build.py` копирует VERSION, иконку, MIT LICENSE, README RU/EN,
  SETUP_GOOGLE.md и только публичный `config/README.md`, затем создаёт переносимый manifest
- `frozen_smoke.py` запускает собранный EXE только в offscreen-режиме с
  изолированными данными и проверяет код выхода, stdout, stderr и лог
- `SpecCompiler.pyw` использует тот же `build.ps1`, без обходного PyInstaller
- Итоговая папка: `YouTubePrivateUploader\` в корне проекта
- Нормальный интерактивный запуск сборка и установщик не выполняют

После проверенной сборки `Build_Tools/build_installer.py` создаёт установщик
Inno Setup 6 на системном «Рабочем столе»:

```powershell
.\.venv\Scripts\python.exe .\Build_Tools\build_installer.py
```

Сборщик создаёт временную чистую копию: `client_secret.json`, токен,
пользовательские настройки, шаблоны и логи не входят в публичный installer.
Мастер Inno Setup использует только `Russian.isl`: его стандартные кнопки и
сообщения остаются русскими независимо от языка Windows. Англоязычная страница
соглашения в мастере не показывается; оригинал MIT `LICENSE` входит в папку
установленного приложения.
Установщик во время запуска проверяет наличие диска D и предлагает
`D:\Apps\YouTubePrivateUploader`; при отсутствии D предлагает
`C:\Apps\YouTubePrivateUploader`. Для записи в корень диска он запрашивает
права администратора. Папка приложения остаётся портативной; галочка запуска
после установки доступна пользователю и включена по умолчанию.

## Релиз

- Версия: `VERSION` (SemVer) + `RELEASE_NOTES.md`
- Release commit: `"Комментарий" [HH:mm:ss]`, теги `vX.Y.Z` + числовой tag
  (см. skills `release-workflow`, `git-numeric-tags`)
- Публичный orphan-снимок не должен включать `handoff.md`, `.agents`, Postman,
  локальный OAuth-файл или собранную папку. Перед отправкой проверить все refs,
  dry-run, backup игнорируемых ценных файлов и содержимое установщика.
