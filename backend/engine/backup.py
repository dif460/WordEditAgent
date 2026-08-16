"""备份与审计。"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.config import settings


def backup_file(src: str, backup_dir: str | None = None) -> Path:
    """把原始 docx 备份到指定目录，返回备份路径。"""
    src_path = Path(src)
    if backup_dir:
        bd = Path(backup_dir)
    else:
        bd = settings.output_path / "backups"
    bd.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dst = bd / f"{src_path.stem}_{stamp}{src_path.suffix}"
    shutil.copy2(src_path, dst)
    return dst
