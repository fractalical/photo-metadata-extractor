"""Photo Metadata Extractor — main entry point.

Usage:
    photo-extract --root-dir /path/to/photos
    PME_ROOT_DIR=/photos python -m src.main
"""

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.config import AppConfig
from src.csv_writer import build_record, load_existing_records, save_records
from src.pipeline import ProcessingPipeline
from src.scanner import scan_directory
from src.schemas import PhotoRecord

# Configure loguru: remove default, add stderr with color
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
    level="INFO",
    colorize=True,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract photo metadata using NPU-accelerated models",
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default=None,
        help="Root directory to scan (overrides PME_ROOT_DIR env var)",
    )
    parser.add_argument(
        "--csv-filename",
        type=str,
        default=None,
        help="Output CSV filename (default: photo_metadata.csv)",
    )
    parser.add_argument(
        "--npu-device",
        type=str,
        default=None,
        choices=["NPU", "GPU", "CPU"],
        help="OpenVINO device to use (default: NPU with fallback)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Reprocess all files (ignore existing CSV records)",
    )
    parser.add_argument(
        "--num-colors",
        type=int,
        default=None,
        help="Number of dominant colors to extract (default: 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Build config from env vars + CLI overrides
    overrides: dict = {}
    if args.root_dir:
        overrides["root_dir"] = args.root_dir
    if args.csv_filename:
        overrides["csv_filename"] = args.csv_filename
    if args.npu_device:
        overrides["npu_device"] = args.npu_device
    if args.no_skip:
        overrides["skip_existing"] = False
    if args.num_colors:
        overrides["num_colors"] = args.num_colors

    try:
        config = AppConfig(**overrides)
    except Exception as e:
        logger.error("Configuration error: {}", e)
        logger.info("Set PME_ROOT_DIR env var or pass --root-dir /path/to/photos")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Photo Metadata Extractor")
    logger.info("Root directory : {}", config.root_dir)
    logger.info("Output CSV     : {}", config.csv_path)
    logger.info("NPU device     : {}", config.npu_device)
    logger.info("Skip existing  : {}", config.skip_existing)
    logger.info("=" * 60)

    # 1. Scan for images
    scans = scan_directory(config)
    if not scans:
        logger.warning("No image files found. Exiting.")
        sys.exit(0)

    # 2. Load existing records for incremental mode
    existing: dict[str, PhotoRecord] = {}
    if config.skip_existing:
        existing = load_existing_records(config.csv_path)

    # Filter out already-processed files (unless file was modified)
    to_process = []
    for scan in scans:
        abs_path = str(scan.path)
        if abs_path in existing:
            record = existing[abs_path]
            # Re-process if file was modified after last processing
            if scan.updated_at > record.last_processing_date:
                logger.debug("File modified, will reprocess: {}", scan.file_name)
                to_process.append(scan)
            else:
                logger.debug("Skipping already processed: {}", scan.file_name)
        else:
            to_process.append(scan)

    logger.info(
        "{} files to process ({} skipped as already up-to-date)",
        len(to_process),
        len(scans) - len(to_process),
    )

    if not to_process:
        logger.info("Nothing new to process. CSV is up to date.")
        sys.exit(0)

    # 3. Process images — each worker thread gets its own pipeline/session
    thread_local = threading.local()

    def _init_worker():
        thread_local.pipeline = ProcessingPipeline(config)

    def _process(scan):
        return thread_local.pipeline.process_image(scan)

    # 4. Process images in batches with progress
    next_id = max((r.id for r in existing.values()), default=0) + 1
    all_records = dict(existing)  # Copy existing records
    processed_count = 0
    failed_count = 0
    start_time = time.monotonic()

    from tqdm import tqdm

    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=config.max_workers,
                            initializer=_init_worker) as executor:
        futures = {executor.submit(_process, scan): scan for scan in to_process}

        for future in tqdm(as_completed(futures), total=len(to_process), desc="Processing", unit="img"):
            scan = futures[future]
            try:
                metadata = future.result()
            except Exception as exc:
                logger.warning("Unexpected error processing {}: {}", scan.file_name, exc)
                metadata = None

            if metadata is None:
                with lock:
                    failed_count += 1
                continue

            abs_path = str(scan.path)
            with lock:
                record_id = existing[abs_path].id if abs_path in existing else next_id
                if abs_path not in existing:
                    next_id += 1
                record = build_record(
                    record_id=record_id,
                    file_name=scan.file_name,
                    absolute_path=abs_path,
                    file_extension=scan.extension,
                    created_at=scan.created_at,
                    updated_at=scan.updated_at,
                    metadata=metadata,
                )
                all_records[abs_path] = record
                processed_count += 1
                should_save = processed_count % config.batch_size == 0
                snapshot = list(all_records.values()) if should_save else None

            if should_save:
                save_records(config.csv_path, snapshot)

    # 5. Final save
    save_records(config.csv_path, list(all_records.values()))

    elapsed = time.monotonic() - start_time
    logger.info("=" * 60)
    logger.info("Done! Processed {} images in {:.1f}s", processed_count, elapsed)
    if failed_count:
        logger.warning("{} images failed to process", failed_count)
    logger.info(
        "Speed: {:.1f} img/s",
        processed_count / elapsed if elapsed > 0 else 0,
    )
    logger.info("CSV saved: {}", config.csv_path)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
