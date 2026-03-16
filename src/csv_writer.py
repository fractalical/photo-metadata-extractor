"""CSV persistence layer with incremental update support."""

import csv
from datetime import datetime, timezone
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
                    def _parse_dt(s: str) -> datetime:
                        dt = datetime.fromisoformat(s)
                        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

                    record = PhotoRecord(
                        id=int(row["id"]),
                        file_name=row["file_name"],
                        absolute_path=row["absolute_path"],
                        file_extension=row["file_extension"],
                        created_at=_parse_dt(row["created_at"]),
                        updated_at=_parse_dt(row["updated_at"]),
                        last_processing_date=_parse_dt(row["last_processing_date"]),
                        metadata=row["metadata"],
                    )
                    records[record.absolute_path] = record
                except (KeyError, ValueError) as e:
                    logger.bind(log_key="log.csv_row_error", log_params={"e": str(e)}).warning("Skipping malformed CSV row: {}", e)
        logger.bind(log_key="log.csv_loaded", log_params={"n": len(records)}).info("Loaded {} existing records from CSV", len(records))
    except Exception as e:
        logger.bind(log_key="log.csv_read_error", log_params={"path": str(csv_path), "e": str(e)}).error("Failed to read CSV {}: {}", csv_path, e)

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

    logger.bind(log_key="log.csv_saved", log_params={"n": len(records), "path": str(csv_path)}).info("Saved {} records to {}", len(records), csv_path)


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
        last_processing_date=datetime.now(tz=timezone.utc),
        metadata=metadata.model_dump_json(),
    )
