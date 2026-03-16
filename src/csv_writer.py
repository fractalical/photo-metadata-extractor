"""CSV persistence layer with incremental update support."""

import csv
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.schemas import ImageMetadata, PhotoRecord


def load_existing_records(csv_path: Path) -> dict[str, PhotoRecord]:
    """Load existing CSV into a dict keyed by absolute_path.

    Returns empty dict if CSV doesn't exist.
    """
    if not csv_path.exists():
        return {}

    records: dict[str, PhotoRecord] = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    record = PhotoRecord(
                        id=int(row["id"]),
                        file_name=row["file_name"],
                        absolute_path=row["absolute_path"],
                        file_extension=row["file_extension"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        last_processing_date=datetime.fromisoformat(
                            row["last_processing_date"]
                        ),
                        metadata=row["metadata"],
                    )
                    records[record.absolute_path] = record
                except (KeyError, ValueError) as e:
                    logger.warning("Skipping malformed CSV row: {}", e)
        logger.info("Loaded {} existing records from CSV", len(records))
    except Exception as e:
        logger.error("Failed to read CSV {}: {}", csv_path, e)

    return records


def save_records(csv_path: Path, records: list[PhotoRecord]) -> None:
    """Write all records to CSV (overwrites)."""
    columns = PhotoRecord.csv_columns()
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for record in sorted(records, key=lambda r: r.id):
            row = record.model_dump()
            # Serialize datetimes to ISO format
            for key in ("created_at", "updated_at", "last_processing_date"):
                row[key] = row[key].isoformat()
            writer.writerow(row)

    logger.info("Saved {} records to {}", len(records), csv_path)


def build_record(
    record_id: int,
    file_name: str,
    absolute_path: str,
    file_extension: str,
    created_at: datetime,
    updated_at: datetime,
    metadata: ImageMetadata,
) -> PhotoRecord:
    """Create a PhotoRecord from scan result + extracted metadata."""
    return PhotoRecord(
        id=record_id,
        file_name=file_name,
        absolute_path=absolute_path,
        file_extension=file_extension,
        created_at=created_at,
        updated_at=updated_at,
        last_processing_date=datetime.now(),
        metadata=metadata.model_dump_json(),
    )
