"""Build a credential-free Inno installer from the verified onedir folder."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "YouTubePrivateUploader"
SPEC = ROOT / "Build_Tools" / "YouTubePrivateUploader.iss"
PRIVATE_NAMES = {"client_secret.json", "token.json", "settings.json", "templates.json", ".installation-id"}


def find_iscc() -> Path:
    candidates = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Inno Setup 6 ISCC.exe is required")


def excluded(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name.casefold() in PRIVATE_NAMES or name.casefold().endswith(".log")
    }


def build(output_dir_override: Path | None = None) -> Path:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest = json.loads((APP_DIR / "RUNTIME_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest["application"]["release_version"] != version:
        raise RuntimeError("Build manifest version differs from VERSION")
    if manifest["qt_runtime"]["scan_root"] != ".":
        raise RuntimeError("Build manifest contains a machine-specific runtime path")
    if not (APP_DIR / "YouTubePrivateUploader.exe").is_file():
        raise FileNotFoundError("Verified onedir executable is missing")
    if not (APP_DIR / "LICENSE").is_file():
        raise FileNotFoundError("LICENSE is missing from the onedir build")

    sys.path.insert(0, str(ROOT))
    from src.config import desktop_dir

    output_dir = (
        output_dir_override.resolve(strict=True)
        if output_dir_override is not None
        else desktop_dir().resolve(strict=True)
    )
    installer = output_dir / f"YouTubePrivateUploader_v{version}_Setup.exe"
    if installer.exists():
        raise FileExistsError(f"Refusing to overwrite an installer: {installer}")

    with tempfile.TemporaryDirectory(prefix="youtube-uploader-installer-") as temp:
        stage = Path(temp) / "YouTubePrivateUploader"
        shutil.copytree(APP_DIR, stage, ignore=excluded)
        (stage / "config").mkdir(exist_ok=True)
        if any(path.name.casefold() in PRIVATE_NAMES for path in stage.rglob("*")):
            raise RuntimeError("Private runtime data entered the installer stage")
        command = [
            str(find_iscc()),
            f"/DAppVersion={version}",
            f"/DSourceDir={stage}",
            f"/O{output_dir}",
            str(SPEC),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"ISCC failed: {result.stdout}\n{result.stderr}")
        if not installer.is_file() or installer.stat().st_size == 0:
            raise RuntimeError("ISCC reported success without a nonempty installer")
    print(f"Installer: {installer} ({installer.stat().st_size} bytes)")
    return installer


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    build(args.output_dir)
