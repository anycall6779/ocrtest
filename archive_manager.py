# -*- coding: utf-8 -*-
"""오래된 OCR 산출물을 프로젝트 backup 폴더로 이동한다."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".gif", ".heic",
}


@dataclass
class ArchiveResult:
    excel_moved: int = 0
    images_moved: int = 0
    skipped: int = 0
    errors: int = 0


def _unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination
    counter = 1
    while True:
        candidate = destination.with_name(f"{destination.stem}_{counter}{destination.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _move_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(_unique_destination(destination)))


def archive_expired_files(
    base_dir: str,
    upload_dir: Optional[str] = None,
    retention_days: float = 2,
    now: Optional[float] = None,
) -> ArchiveResult:
    """48시간이 지난 루트 Excel과 uploads 이미지를 backup 하위로 이동한다.

    Excel은 ``backup/excel``로, 이미지는 기존 uploads 상대 경로를 유지한 채
    ``backup/images``로 이동한다. 파일 수정시각을 기준으로 판단한다.
    """
    base = Path(base_dir).resolve()
    uploads = Path(upload_dir).resolve() if upload_dir else base / "uploads"
    backup_root = base / "backup"
    excel_backup = backup_root / "excel"
    image_backup = backup_root / "images"
    cutoff = (time.time() if now is None else now) - retention_days * 24 * 60 * 60
    result = ArchiveResult()

    # 프로젝트 최상단에 생성되는 주차단속 Excel 파일만 이동한다.
    for source in base.glob("*.xlsx"):
        try:
            if not source.is_file() or source.stat().st_mtime > cutoff:
                result.skipped += 1
                continue
            _move_file(source, excel_backup / source.name)
            result.excel_moved += 1
        except (OSError, PermissionError) as exc:
            result.errors += 1
            print(f"⚠️ Excel 보관 이동 실패: {source} ({exc})")

    if uploads.is_dir():
        image_sources = [
            path for path in uploads.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        for source in image_sources:
            try:
                if source.stat().st_mtime > cutoff:
                    result.skipped += 1
                    continue
                relative = source.relative_to(uploads)
                _move_file(source, image_backup / relative)
                result.images_moved += 1
            except (OSError, PermissionError, ValueError) as exc:
                result.errors += 1
                print(f"⚠️ 이미지 보관 이동 실패: {source} ({exc})")

        # 이동 후 비어 있는 uploads 하위 폴더만 아래에서부터 정리한다.
        for directory in sorted((p for p in uploads.rglob("*") if p.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass

    return result
