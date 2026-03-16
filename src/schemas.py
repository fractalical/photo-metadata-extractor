"""Data schemas for photo metadata extraction."""

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class ContentCategory(StrEnum):
    """High-level content categories for photos."""

    PORTRAIT = "portrait"
    CITY = "city"
    NATURE = "nature"
    ARCHITECTURE = "architecture"
    FOOD = "food"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    INDOOR = "indoor"
    SPORT = "sport"
    DOCUMENT = "document"
    OTHER = "other"


class DominantColor(BaseModel):
    """A dominant color extracted from the image."""

    hex: str = Field(description="Hex color code, e.g. #FF5733")
    name: str = Field(description="Closest CSS color name")
    percentage: float = Field(description="Percentage of image area (0-100)")


class ImageMetadata(BaseModel):
    """Extracted metadata for a single image."""

    content_categories: list[ContentCategory] = Field(
        default_factory=list,
        description="Detected content categories (top 1-3)",
    )
    content_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each detected category",
    )
    dominant_colors: list[DominantColor] = Field(
        default_factory=list,
        description="Top 3-5 dominant colors",
    )
    width: int = 0
    height: int = 0


class PhotoRecord(BaseModel):
    """A single row in the output CSV."""

    id: int
    file_name: str
    absolute_path: str
    file_extension: str
    created_at: datetime = Field(description="File creation timestamp")
    updated_at: datetime = Field(description="File last-modified timestamp")
    last_processing_date: datetime = Field(
        default_factory=datetime.now,
        description="When this record was last processed",
    )
    metadata: str = Field(description="JSON-serialized ImageMetadata")

    @classmethod
    def csv_columns(cls) -> list[str]:
        return list(cls.model_fields.keys())


class ScanResult(BaseModel):
    """Result of scanning a single file."""

    path: Path
    file_name: str
    extension: str
    created_at: datetime
    updated_at: datetime
    size_bytes: int
