"""Return the small trusted PATH used for every Windows PyInstaller build."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def trusted_path(python_executable: Path) -> str:
    python_executable = python_executable.resolve(strict=True)
    result = subprocess.run(
        [
            str(python_executable),
            "-c",
            ("import json,sys,PySide6; print(json.dumps({"
             "'prefix':sys.prefix,'base':sys.base_prefix,'pyside':PySide6.__file__}))"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    runtime = json.loads(result.stdout)
    venv_root = Path(runtime["prefix"]).resolve(strict=True)
    if python_executable.parent != venv_root / "Scripts":
        raise ValueError("Selected Python is not from the project virtual environment")
    pyside_root = Path(runtime["pyside"]).resolve(strict=True).parent
    if not pyside_root.is_relative_to(venv_root):
        raise ValueError("PySide6 is not installed in the selected environment")
    system_root = Path(os.environ["SystemRoot"]).resolve(strict=True)
    base_root = Path(runtime["base"]).resolve(strict=True)
    candidates = (
        python_executable.parent,
        pyside_root,
        pyside_root / "Qt" / "bin",
        base_root,
        base_root / "DLLs",
        system_root / "System32",
    )
    paths = [str(path) for path in candidates if path.is_dir()]
    if not paths or str(system_root / "System32") not in paths:
        raise RuntimeError("Trusted runtime PATH is incomplete")
    return os.pathsep.join(dict.fromkeys(paths))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, type=Path)
    args = parser.parse_args()
    print(trusted_path(args.python))
