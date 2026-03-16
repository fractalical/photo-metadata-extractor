"""Recursive image file scanner."""

import os
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.config import AppConfig
from src.schemas import ScanResult


def _get_timestamps(path: Path) -> tuple[datetime, datetime]:
    """Get creation and modification timestamps for a file."""
    stat = path.stat()
    # st_birthtime on macOS/Windows, fallback to st_ctime
    created = getattr(stat, "st_birthtime", stat.st_ctime)
    modified = stat.st_mtime
    return (
        datetime.fromtimestamp(created, tz=timezone.utc),
        datetime.fromtimestamp(modified, tz=timezone.utc),
    )


def scan_directory(config: AppConfig) -> list[ScanResult]:
    """Recursively scan root_dir for image files.

    Returns list of ScanResult sorted by path.
    Skips hidden files/directories and the output CSV.
    """
    results: list[ScanResult] = []
    root = config.root_dir.resolve()

    if not root.is_dir():
        raise FileNotFoundError(f"Root directory not found: {root}")

    logger.info("Scanning directory: {}", root)
    extensions = {ext.lower() for ext in config.image_extensions}

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for fname in filenames:
            if fname.startswith("."):
                continue

            fpath = Path(dirpath) / fname
            ext = fpath.suffix.lower()

            if ext not in extensions:
                continue

            try:
                created_at, updated_at = _get_timestamps(fpath)
                results.append(
                    ScanResult(
                        path=fpath.resolve(),
                        file_name=fname,
                        extension=ext,
                        created_at=created_at,
                        updated_at=updated_at,
                        size_bytes=fpath.stat().st_size,
                    )
                )
            except OSError as e:
                logger.warning("Cannot read file {}: {}", fpath, e)

    results.sort(key=lambda r: r.path)
    logger.info("Found {} image files", len(results))
    return results
