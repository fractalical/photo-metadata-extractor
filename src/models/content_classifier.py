"""Content classifier using MobileNetV2 ONNX model.

Maps ImageNet-1000 classes to high-level content categories.
Supports Intel NPU (OpenVINO), AMD XDNA NPU (Vitis AI), and CPU fallback.
AMD NPU requires INT8-quantized model — see src/models/quantize.py.
"""

import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

from src.models.base import BaseONNXModel
from src.schemas import ContentCategory

# MobileNetV2 ONNX from ONNX Model Zoo
_MODEL_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/classification/"
    "mobilenet/model/mobilenetv2-12.onnx"
)
_LABELS_URL = (
    "https://raw.githubusercontent.com/anishathalye/imagenet-simple-labels/"
    "master/imagenet-simple-labels.json"
)

# Mapping from ImageNet class substrings to our categories.
# Order matters: first match wins for each class label.
_CATEGORY_MAP: list[tuple[list[str], ContentCategory]] = [
    # Animals
    (
        [
            "dog", "cat", "bird", "fish", "horse", "elephant", "bear", "monkey",
            "rabbit", "snake", "turtle", "whale", "shark", "tiger", "lion",
            "zebra", "giraffe", "penguin", "owl", "parrot", "hamster", "mouse",
            "spider", "insect", "bee", "butterfly", "ant", "crab", "lobster",
            "snail", "lizard", "frog", "hen", "rooster", "goose", "duck",
            "swan", "flamingo", "pelican", "hummingbird", "eagle", "hawk",
            "vulture", "ox", "bison", "ram", "sheep", "goat", "pig",
            "hippopotamus", "rhinoceros", "gorilla", "chimpanzee", "koala",
            "panda", "jellyfish", "coral", "starfish", "sea urchin",
            "goldfish", "puffer", "eel", "ray", "dolphin",
        ],
        ContentCategory.NATURE,
    ),
    # Vehicles
    (
        [
            "car", "truck", "bus", "motorcycle", "bicycle", "train", "airplane",
            "boat", "ship", "ambulance", "taxi", "fire engine", "tractor",
            "van", "jeep", "convertible", "minivan", "limousine", "cab",
            "scooter", "moped", "snowmobile", "go-kart", "forklift",
        ],
        ContentCategory.VEHICLE,
    ),
    # Food
    (
        [
            "food", "pizza", "burger", "sandwich", "cake", "fruit", "bread",
            "soup", "salad", "ice cream", "coffee", "cup", "plate", "bowl",
            "bottle", "wine", "beer", "menu", "restaurant", "banana", "apple",
            "orange", "strawberry", "lemon", "pineapple", "mushroom", "broccoli",
            "corn", "pretzel", "bagel", "cheeseburger", "hotdog", "taco",
            "burrito", "espresso", "guacamole", "meat loaf", "potpie",
        ],
        ContentCategory.FOOD,
    ),
    # Sports
    (
        [
            "ball", "tennis", "soccer", "basketball", "baseball", "golf",
            "ski", "snowboard", "surfboard", "volleyball", "rugby",
            "ping-pong", "racket", "barbell", "dumbbell",
        ],
        ContentCategory.SPORT,
    ),
    # Architecture / city
    (
        [
            "church", "castle", "palace", "tower", "bridge", "mosque",
            "cathedral", "monastery", "lighthouse", "skyscraper", "dome",
            "triumphal arch", "obelisk", "library", "theater", "cinema",
            "barn", "greenhouse", "beacon",
        ],
        ContentCategory.ARCHITECTURE,
    ),
    (
        [
            "street", "traffic", "crosswalk", "parking", "highway",
            "streetcar", "trolleybus", "mailbox", "pay-phone",
        ],
        ContentCategory.CITY,
    ),
    # Nature / landscape
    (
        [
            "mountain", "lake", "river", "ocean", "beach", "forest", "valley",
            "cliff", "volcano", "waterfall", "desert", "meadow", "flower",
            "tree", "rock", "cloud", "sunset", "sunrise", "seashore",
            "lakeside", "alp", "promontory", "sandbar", "coral reef",
            "geyser",
        ],
        ContentCategory.NATURE,
    ),
    # Indoor
    (
        [
            "desk", "chair", "table", "sofa", "bed", "lamp", "keyboard",
            "monitor", "television", "microwave", "oven", "refrigerator",
            "wardrobe", "bookshelf", "bathtub", "shower", "toilet",
            "washer", "iron", "vacuum", "remote control", "laptop",
            "desktop computer", "notebook", "screen",
        ],
        ContentCategory.INDOOR,
    ),
    # Document
    (
        [
            "book", "newspaper", "envelope", "notebook", "letter", "binder",
            "comic book", "crossword",
        ],
        ContentCategory.DOCUMENT,
    ),
    # Portrait (very few ImageNet classes map here; we rely on face detection separately)
    (
        ["mask", "wig", "sunglasses", "sunglass"],
        ContentCategory.PORTRAIT,
    ),
]


def _classify_label(label: str) -> ContentCategory:
    """Map a single ImageNet label to our category."""
    label_lower = label.lower()
    for keywords, category in _CATEGORY_MAP:
        for kw in keywords:
            if kw in label_lower:
                return category
    return ContentCategory.OTHER


def needs_quantization(fp32_path: Path, int8_path: Path, execution_provider: str = "auto") -> bool:
    """Return True when Vitis AI EP is requested but INT8 model is missing."""
    from src.models.base import detect_npu_vendor
    is_vitis = (
        execution_provider == "VitisAIExecutionProvider"
        or (execution_provider == "auto" and detect_npu_vendor() == "amd")
    )
    return is_vitis and not int8_path.exists()


def auto_quantize(
    fp32_path: Path,
    int8_path: Path,
    image_paths: list[Path],
    num_samples: int = 100,
) -> bool:
    """Quantize fp32_path → int8_path using image_paths as calibration data.

    Returns True on success, False on any error.
    """
    import shutil
    import tempfile

    from src.models.quantize import quantize_model

    try:
        if not fp32_path.exists():
            import urllib.request
            fp32_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Downloading FP32 model for quantization...")
            urllib.request.urlretrieve(_MODEL_URL, str(fp32_path))
        samples = image_paths[:num_samples]
        if not samples:
            raise ValueError("No calibration images available")
        with tempfile.TemporaryDirectory() as tmp:
            for p in samples:
                shutil.copy2(p, tmp)
            quantize_model(
                input_model=fp32_path,
                output_model=int8_path,
                calibration_dir=Path(tmp),
                num_samples=num_samples,
            )
        return True
    except Exception as exc:
        logger.warning("Auto-quantization failed: {}", exc)
        return False


class ContentClassifier(BaseONNXModel):
    """MobileNetV2-based content classifier with ImageNet→category mapping.

    For AMD XDNA NPU: uses INT8-quantized model if available.
    For Intel NPU / CPU: uses FP32 model directly.
    """

    def __init__(
        self,
        cache_dir: Path,
        execution_provider: str = "auto",
        npu_device: str = "NPU",
        vitis_config: Path | None = None,
    ) -> None:
        model_path = self._ensure_model(cache_dir, execution_provider)
        self.labels = self._load_labels(cache_dir)
        self._label_to_category = {
            label: _classify_label(label) for label in self.labels
        }
        super().__init__(
            model_path,
            execution_provider,
            npu_device,
            vitis_config=vitis_config,
        )

    @staticmethod
    def _ensure_model(cache_dir: Path, execution_provider: str = "auto") -> Path:
        """Download MobileNetV2 ONNX. Use INT8 version for AMD if available."""
        from src.models.base import detect_npu_vendor

        cache_dir.mkdir(parents=True, exist_ok=True)
        fp32_path = cache_dir / "mobilenetv2-12.onnx"
        int8_path = cache_dir / "mobilenetv2-12-int8.onnx"

        # Download FP32 model if not cached
        if not fp32_path.exists():
            logger.info("Downloading MobileNetV2 ONNX model...")
            urllib.request.urlretrieve(_MODEL_URL, str(fp32_path))
            logger.info("Model saved to {}", fp32_path)

        # For AMD NPU: prefer quantized INT8 model
        vendor = detect_npu_vendor() if execution_provider == "auto" else ""
        is_amd = vendor == "amd" or execution_provider == "VitisAIExecutionProvider"

        if is_amd and int8_path.exists():
            logger.info("Using INT8 quantized model for AMD NPU: {}", int8_path)
            return int8_path
        elif is_amd and not int8_path.exists():
            logger.warning(
                "AMD NPU detected but INT8 model not ready at {}. "
                "Falling back to FP32 model (will run on CPU).",
                int8_path,
            )

        return fp32_path

    @staticmethod
    def _load_labels(cache_dir: Path) -> list[str]:
        """Download and cache ImageNet labels."""
        labels_path = cache_dir / "imagenet_labels.json"
        if not labels_path.exists():
            logger.info("Downloading ImageNet labels...")
            urllib.request.urlretrieve(_LABELS_URL, str(labels_path))
        with open(labels_path) as f:
            return json.load(f)

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for MobileNetV2: resize, normalize, NCHW format.

        Args:
            image: BGR image from cv2.imread, any size.

        Returns:
            np.ndarray of shape [1, 3, 224, 224], float32.
        """
        img = cv2.resize(image, (224, 224))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0

        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std

        # HWC → NCHW
        img = np.transpose(img, (2, 0, 1))
        return np.expand_dims(img, axis=0)

    def predict(self, image: np.ndarray) -> dict:
        """Classify image content.

        Args:
            image: Raw BGR image (from cv2.imread).

        Returns:
            dict with 'categories' and 'scores' keys.
        """
        input_tensor = self.preprocess(image)
        outputs = self.session.run(None, {self.input_name: input_tensor})
        logits = outputs[0][0]

        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()

        # Aggregate probabilities by our categories
        category_scores: dict[ContentCategory, float] = {}
        for idx, prob in enumerate(probs):
            if idx >= len(self.labels):
                break
            cat = self._label_to_category[self.labels[idx]]
            category_scores[cat] = category_scores.get(cat, 0.0) + float(prob)

        # Sort by score descending
        sorted_cats = sorted(category_scores.items(), key=lambda x: -x[1])

        return {
            "categories": [cat for cat, _ in sorted_cats],
            "scores": {cat.value: round(score, 4) for cat, score in sorted_cats},
        }
