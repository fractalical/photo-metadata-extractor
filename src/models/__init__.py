"""ML models for photo metadata extraction."""

from src.models.color_extractor import ColorExtractor
from src.models.content_classifier import ContentClassifier

__all__ = ["ContentClassifier", "ColorExtractor"]

# Quantization utilities available as:
#   from src.models.quantize import quantize_model
#   python -m src.models.quantize --help
