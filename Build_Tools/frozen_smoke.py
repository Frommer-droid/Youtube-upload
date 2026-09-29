"""Initialize and exit the frozen GUI offscreen without OAuth or user input."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def smoke(executable: Path) -> None:
    executable = executable.resolve(strict=True)
    if not executable.is_file():
        raise FileNotFoundError(executable)
    with tempfile.TemporaryDirectory(prefix="youtube-uploader-frozen-smoke-") as data:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["YOUTUBE_PRIVATE_UPLOADER_FROZEN_SMOKE"] = "1"
        env["YOUTUBE_PRIVATE_UPLOADER_DATA_DIR"] = data
        result = subprocess.run(
            [str(executable)],
            cwd=executable.parent,
            env=env,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode or result.stdout or result.stderr:
            raise RuntimeError(
                f"Frozen smoke failed: exit={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        log_files = list((Path(data) / "logs").glob("*.log"))
        logs = "\n".join(path.read_text(encoding="utf-8") for path in log_files)
        for marker in ("Приложение запущено", "Главное окно показано", "Приложение завершено"):
            if marker not in logs:
                raise RuntimeError(f"Frozen smoke log marker missing: {marker}")
    print("Frozen smoke: exit 0, empty stdout/stderr, GUI initialized and closed")


if __name__ == "__main__":
    smoke(Path(sys.argv[1]))
