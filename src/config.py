"""Application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Configuration loaded from environment variables."""

    model_config = {"env_prefix": "PME_"}

    root_dir: Path = Field(
        description="Root directory to scan for photos",
    )
    csv_filename: str = Field(
        default="photo_metadata.csv",
        description="Output CSV filename (created in root_dir)",
    )
    batch_size: int = Field(
        default=16,
        description="Number of images to process in a batch",
    )
    num_colors: int = Field(
        default=5,
        description="Number of dominant colors to extract",
    )
    top_categories: int = Field(
        default=3,
        description="Max number of content categories per image",
    )
    confidence_threshold: float = Field(
        default=0.12,
        description="Minimum confidence to include a category",
    )
    image_extensions: set[str] = Field(
        default={".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"},
        description="Supported image file extensions",
    )
    execution_provider: str = Field(
        default="auto",
        description="ONNX Runtime EP: auto, OpenVINOExecutionProvider, VitisAIExecutionProvider, CPUExecutionProvider",
    )
    npu_device: str = Field(
        default="NPU",
        description="OpenVINO device: NPU, GPU, CPU. Falls back to CPU if unavailable",
    )
    model_cache_dir: Path = Field(
        default=Path("/app/models"),
        description="Directory to cache downloaded models",
    )
    skip_existing: bool = Field(
        default=True,
        description="Skip files already present in CSV (incremental mode)",
    )
    max_workers: int = Field(
        default=4,
        description="Number of parallel workers for I/O operations",
    )

    @property
    def csv_path(self) -> Path:
        return self.root_dir / self.csv_filename
