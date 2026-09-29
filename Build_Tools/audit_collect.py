"""Fail a release build if COLLECT contains foreign DLLs or mixed Qt MSVC DLLs."""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

import pefile
import PySide6

MSVC_RUNTIME = {
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
}


def file_version(path: Path) -> tuple[int, int, int, int]:
    image = pefile.PE(str(path), fast_load=False)
    fixed = image.VS_FIXEDFILEINFO[0]
    return (
        fixed.FileVersionMS >> 16,
        fixed.FileVersionMS & 0xFFFF,
        fixed.FileVersionLS >> 16,
        fixed.FileVersionLS & 0xFFFF,
    )


def audit(toc_path: Path) -> None:
    project_root = Path(__file__).resolve().parent.parent
    toc_path = toc_path.resolve(strict=True)
    if not toc_path.is_relative_to(project_root / "Build_Tools" / "build"):
        raise ValueError(f"Unexpected COLLECT path: {toc_path}")
    toc = ast.literal_eval(toc_path.read_text(encoding="utf-8"))
    if not isinstance(toc, tuple) or len(toc) != 1 or not isinstance(toc[0], list):
        raise ValueError("Unexpected COLLECT-00.toc structure")
    entries = toc[0]
    allowed = [
        project_root,
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        Path(os.environ["SystemRoot"]).resolve(),
    ]
    pyside_root = Path(PySide6.__file__).resolve().parent
    binaries = []
    root_runtime = {}
    foreign = []
    for destination, source, kind in entries:
        if kind not in {"BINARY", "EXTENSION"}:
            continue
        binaries.append(destination)
        source_path = Path(source).resolve(strict=True)
        if not any(source_path.is_relative_to(root) for root in allowed):
            foreign.append((destination, source_path))
        if Path(destination).parent == Path("."):
            name = Path(destination).name.casefold()
            if name in MSVC_RUNTIME:
                root_runtime.setdefault(name, []).append(source_path)
    if foreign:
        raise RuntimeError(f"Foreign binary origins: {foreign}")
    if set(root_runtime) != MSVC_RUNTIME or any(
        len(sources) != 1 for sources in root_runtime.values()
    ):
        raise RuntimeError(f"Incomplete or duplicate root MSVC runtime: {root_runtime}")
    if any(sources[0].parent != pyside_root for sources in root_runtime.values()):
        raise RuntimeError(f"Root MSVC runtime is not entirely from PySide6: {root_runtime}")
    versions = {file_version(sources[0]) for sources in root_runtime.values()}
    if len(versions) != 1:
        raise RuntimeError(f"Mixed MSVC runtime versions: {versions}")
    print(
        f"COLLECT audit: {len(binaries)} binaries/extensions, 0 foreign origins, "
        f"5 PySide6 MSVC DLLs at version {next(iter(versions))}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("toc", type=Path)
    audit(parser.parse_args().toc)
