# -*- mode: python ; coding: utf-8 -*-
r"""
PyInstaller spec для Windows desktop-приложения YouTubePrivateUploader (Python/PySide6).

Запуск из корня проекта: .\build.ps1.
"""

import os
import sys
from pathlib import Path

import PySide6
from PyInstaller.building.datastruct import Tree


APP_NAME = "YouTubePrivateUploader"
ENTRYPOINT = "YouTubePrivateUploader.py"

block_cipher = None

spec_path = os.path.abspath(sys.argv[0])
spec_dir = os.path.dirname(spec_path)
project_root = os.path.abspath(os.path.join(spec_dir, ".."))
script_path = os.path.join(project_root, ENTRYPOINT)
src_dir = os.path.join(project_root, "src")

# Отдельные файлы из корня проекта, которые должны попасть рядом с exe.
ROOT_DATA_FILES = (
    "VERSION",
    "logo.ico",
    "LICENSE",
)

# Папки данных: (исходная_папка_в_корне, путь_в_сборке). Для этого проекта нет.
DATA_DIRECTORIES = ()

# Только реальные dynamic imports проекта. Google-библиотеки покрываются хуками PyInstaller.
HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
]

# Тяжёлые библиотеки, не нужные приложению в рантайме.
EXCLUDES = [
    "tkinter",
    "matplotlib",
    "PIL",
    "torch",
    "tensorflow",
]

# Дополнительные доверенные каталоги native runtime можно перечислить здесь.
# По умолчанию сборка принимает DLL только из проекта, выбранного Python/venv
# и Windows System32.
PROJECT_BINARY_ALLOWLIST = ()
QT_MSVC_RUNTIME_FILES = (
    "MSVCP140.dll",
    "MSVCP140_1.dll",
    "MSVCP140_2.dll",
    "VCRUNTIME140.dll",
    "VCRUNTIME140_1.dll",
)


def validate_build_path():
    """Reject native DLL search paths outside the selected runtime."""
    system_root = Path(os.environ["SystemRoot"]).resolve(strict=True)
    pyside_root = Path(PySide6.__file__).resolve(strict=True).parent
    base_root = Path(sys.base_prefix).resolve(strict=True)
    trusted = {
        path.resolve(strict=True)
        for path in (
            Path(sys.executable).parent,
            pyside_root,
            pyside_root / "Qt" / "bin",
            base_root,
            base_root / "DLLs",
            system_root / "System32",
        )
        if path.is_dir()
    }
    actual = [Path(value).resolve(strict=True) for value in os.environ["PATH"].split(os.pathsep) if value]
    foreign = [str(path) for path in actual if path not in trusted]
    if foreign or system_root / "System32" not in actual:
        raise SystemExit(f"[ERROR] Unsafe PyInstaller PATH: {foreign}")
    print("[OK] minimal trusted PyInstaller PATH")


def enforce_qt_msvc_runtime(binaries):
    """Use one complete, version-consistent MSVC runtime beside the exe."""
    pyside_root = Path(PySide6.__file__).resolve().parent
    runtime_names = {name.casefold() for name in QT_MSVC_RUNTIME_FILES}
    binaries[:] = [
        entry
        for entry in binaries
        if not (
            len(entry) > 1
            and Path(entry[0]).parent == Path(".")
            and Path(entry[0]).name.casefold() in runtime_names
        )
    ]
    for filename in QT_MSVC_RUNTIME_FILES:
        source = pyside_root / filename
        if not source.is_file():
            raise SystemExit(f"[ERROR] Missing PySide6 runtime file: {source}")
        binaries.append((filename, str(source), "BINARY"))
    print("[OK] root MSVC runtime pinned to the complete PySide6 set")


def validate_binary_origins(binaries):
    system_root = os.environ.get("SystemRoot")
    allowed_roots = [
        Path(project_root).resolve(),
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
    ]
    if system_root:
        allowed_roots.append(Path(system_root).resolve())
    allowed_roots.extend(Path(path).resolve() for path in PROJECT_BINARY_ALLOWLIST)

    foreign = []
    for entry in binaries:
        source = entry[1] if len(entry) > 1 else None
        if not source:
            foreign.append((entry[0], "<source missing>"))
            continue
        source_path = Path(source).resolve()
        if not any(source_path.is_relative_to(root) for root in allowed_roots):
            foreign.append((entry[0], str(source_path)))

    if foreign:
        details = "\n".join(f"  {name} <- {source}" for name, source in foreign)
        raise SystemExit(
            "[ERROR] PyInstaller обнаружил native binaries из недоверенных "
            f"каталогов:\n{details}"
        )
    print(
        f"[OK] binary origin policy: {len(binaries)} entries, "
        "foreign origins: 0"
    )


def existing_root_files():
    files = []
    for filename in ROOT_DATA_FILES:
        source_path = os.path.join(project_root, filename)
        if os.path.isfile(source_path):
            files.append((source_path, "."))
            print(f"[OK] data file: {filename}")
        else:
            print(f"[SKIP] data file missing: {filename}")
    return files


def existing_qt_translation_files():
    files = []
    pyside_root = os.path.dirname(PySide6.__file__)
    translation_locations = (
        (
            os.path.join(pyside_root, "translations"),
            os.path.join("PySide6", "translations"),
        ),
        (
            os.path.join(pyside_root, "Qt", "translations"),
            os.path.join("PySide6", "Qt", "translations"),
        ),
    )
    for filename in ("qtbase_ru.qm",):
        copied = False
        for translations_dir, target_dir in translation_locations:
            source_path = os.path.join(translations_dir, filename)
            if os.path.isfile(source_path):
                files.append((source_path, target_dir))
                print(f"[OK] Qt translation: {filename} -> {target_dir}")
                copied = True
                break
        if copied:
            continue
        print(f"[SKIP] Qt translation missing: {filename}")
    return files


datas = existing_root_files()
datas += existing_qt_translation_files()

validate_build_path()
a = Analysis(
    [script_path],
    pathex=[project_root, src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[spec_dir],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Reject foreign sources before replacing the root runtime. Otherwise a foreign
# VCRUNTIME entry could disappear from the list without failing the build.
validate_binary_origins(a.binaries)
enforce_qt_msvc_runtime(a.binaries)
validate_binary_origins(a.binaries)

for source_name, target_prefix in DATA_DIRECTORIES:
    source_dir = os.path.join(project_root, source_name)
    if os.path.isdir(source_dir):
        a.datas += Tree(source_dir, prefix=target_prefix)
        print(f"[OK] data directory: {source_name} -> {target_prefix}")
    else:
        print(f"[SKIP] data directory missing: {source_name}")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, "logo.ico")
    if os.path.exists(os.path.join(project_root, "logo.ico"))
    else None,
    version=os.path.join(spec_dir, "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
