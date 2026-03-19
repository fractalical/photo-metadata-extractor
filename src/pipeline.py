"""Processing pipeline: load image → run models → collect metadata."""

import cv2
import numpy as np
from loguru import logger

from src.config import AppConfig
from src.models.color_extractor import ColorExtractor
from src.models.content_classifier import ContentClassifier
from src.schemas import ContentCategory, ImageMetadata, ScanResult

# These ImageNet-derived categories are often false positives when
# a face is confidently detected, so we remove them in that case.
_FACE_FALSE_POSITIVES = {ContentCategory.VEHICLE, ContentCategory.SPORT}


def _face_confidence(image: np.ndarray, cascades: list) -> float:
    """Detect faces and return a portrait confidence score (0–1).

    Scales by face-area ratio: face covering ~5% of the frame → ~0.5.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = image.shape[:2]
    total_face_area = 0

    for cascade in cascades:
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
        )
        if len(faces) > 0:
            total_face_area += sum(int(fw) * int(fh) for (_, _, fw, fh) in faces)

    if total_face_area == 0:
        return 0.0

    ratio = total_face_area / (w * h)
    return float(min(ratio * 5.0, 1.0))


class ProcessingPipeline:
    """Orchestrates model inference for a single image or batch."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

        logger.bind(log_key="log.init_classifier", log_params={"provider": config.npu_device}).info("Initializing content classifier (NPU: {})...", config.npu_device)
        self.classifier = ContentClassifier(
            cache_dir=config.model_cache_dir,
            execution_provider=config.execution_provider,
            npu_device=config.npu_device,
        )

        logger.bind(log_key="log.init_colors").info("Initializing color extractor...")
        self.color_extractor = ColorExtractor(num_colors=config.num_colors)

        # Face detectors — OpenCV built-in Haar cascades, no extra deps
        self._face_cascades = [
            cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            ),
            cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_profileface.xml"
            ),
        ]
        logger.bind(log_key="log.init_face").info("Face detector initialized.")

    def process_image(self, scan: ScanResult) -> ImageMetadata | None:
        """Process a single image file and return metadata.

        Returns None if the image cannot be read.
        """
        image = cv2.imread(str(scan.path), cv2.IMREAD_COLOR)
        if image is None:
            logger.bind(log_key="log.read_error", log_params={"path": str(scan.path)}).warning("Failed to read image: {}", scan.path)
            return None

        h, w = image.shape[:2]

        # Content classification (MobileNetV2 / NPU)
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
            logger.bind(log_key="log.classify_error", log_params={"path": str(scan.path), "e": str(e)}).error("Classification failed for {}: {}", scan.path, e)
            categories = [ContentCategory.OTHER]
            scores = {"other": 1.0}

        # Face detection — overrides / corrects portrait classification
        try:
            face_conf = _face_confidence(image, self._face_cascades)
            if face_conf >= 0.1:
                # Set portrait score from face detector
                scores[ContentCategory.PORTRAIT.value] = round(face_conf, 4)
                if ContentCategory.PORTRAIT not in categories:
                    categories = [ContentCategory.PORTRAIT] + [
                        c for c in categories if c != ContentCategory.PORTRAIT
                    ]

                # Remove known false positives when portrait is strong
                if face_conf >= 0.3:
                    categories = [c for c in categories if c not in _FACE_FALSE_POSITIVES]
                    for fp in _FACE_FALSE_POSITIVES:
                        scores.pop(fp.value, None)

                # Re-sort by score
                categories.sort(key=lambda c: -scores.get(c.value, 0))

        except Exception as e:
            logger.bind(log_key="log.face_error", log_params={"path": str(scan.path), "e": str(e)}).warning("Face detection failed for {}: {}", scan.path, e)

        # Dominant colors (CPU, fast)
        try:
            colors = self.color_extractor.extract(image)
        except Exception as e:
            logger.bind(log_key="log.color_error", log_params={"path": str(scan.path), "e": str(e)}).error("Color extraction failed for {}: {}", scan.path, e)
            colors = []

        return ImageMetadata(
            content_categories=categories,
            content_scores=scores,
            dominant_colors=colors,
            width=w,
            height=h,
        )

    def close(self) -> None:
        """Release ONNX session and CV resources."""
        self.classifier.session = None
        self.color_extractor = None
        self._face_cascades = []

    def process_batch(
        self, scans: list[ScanResult]
    ) -> list[tuple[ScanResult, ImageMetadata | None]]:
        """Process a batch of images. Returns (scan, metadata) pairs."""
        results: list[tuple[ScanResult, ImageMetadata | None]] = []
        for scan in scans:
            metadata = self.process_image(scan)
            results.append((scan, metadata))
        return results
