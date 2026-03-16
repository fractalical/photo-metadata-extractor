"""Processing pipeline: load image → run models → collect metadata."""

import cv2
import numpy as np
from loguru import logger

from src.config import AppConfig
from src.models.color_extractor import ColorExtractor
from src.models.content_classifier import ContentClassifier
from src.schemas import ContentCategory, ImageMetadata, ScanResult


class ProcessingPipeline:
    """Orchestrates model inference for a single image or batch."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

        logger.info("Initializing content classifier (NPU: {})...", config.npu_device)
        self.classifier = ContentClassifier(
            cache_dir=config.model_cache_dir,
            execution_provider=config.execution_provider,
            npu_device=config.npu_device,
        )

        logger.info("Initializing color extractor...")
        self.color_extractor = ColorExtractor(num_colors=config.num_colors)

    def process_image(self, scan: ScanResult) -> ImageMetadata | None:
        """Process a single image file and return metadata.

        Returns None if the image cannot be read.
        """
        image = cv2.imread(str(scan.path), cv2.IMREAD_COLOR)
        if image is None:
            logger.warning("Failed to read image: {}", scan.path)
            return None

        h, w = image.shape[:2]

        # Content classification (runs on NPU)
        try:
            cls_result = self.classifier.predict(image)
            categories = [
                cat
                for cat in cls_result["categories"][: self.config.top_categories]
                if cls_result["scores"].get(cat.value, 0) >= self.config.confidence_threshold
            ]
            scores = {
                cat.value: cls_result["scores"][cat.value]
                for cat in categories
            }
        except Exception as e:
            logger.error("Classification failed for {}: {}", scan.path, e)
            categories = [ContentCategory.OTHER]
            scores = {"other": 1.0}

        # Dominant colors (CPU, fast)
        try:
            colors = self.color_extractor.extract(image)
        except Exception as e:
            logger.error("Color extraction failed for {}: {}", scan.path, e)
            colors = []

        return ImageMetadata(
            content_categories=categories,
            content_scores=scores,
            dominant_colors=colors,
            width=w,
            height=h,
        )

    def process_batch(
        self, scans: list[ScanResult]
    ) -> list[tuple[ScanResult, ImageMetadata | None]]:
        """Process a batch of images. Returns (scan, metadata) pairs."""
        results: list[tuple[ScanResult, ImageMetadata | None]] = []
        for scan in scans:
            metadata = self.process_image(scan)
            results.append((scan, metadata))
        return results
