"""备份与审计。"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.config import settings


def backup_file(src: str) -> Path:
    """把原始 docx 备份到 outputs/backups，返回备份路径。"""
    src_path = Path(src)
    backup_dir = settings.output_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dst = backup_dir / f"{src_path.stem}_{stamp}{src_path.suffix}"
    shutil.copy2(src_path, dst)
    return dst
