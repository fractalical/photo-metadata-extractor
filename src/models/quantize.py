"""Quantize ONNX models for AMD XDNA NPU deployment.

AMD Vitis AI EP requires INT8 or BF16 quantized models.
This script performs post-training static quantization using
onnxruntime's built-in quantizer (compatible with Vitis AI EP).

Usage:
    python -m src.models.quantize \
        --input models/mobilenetv2-12.onnx \
        --output models/mobilenetv2-12-int8.onnx \
        --calibration-dir /path/to/sample/images

If AMD Quark is installed, it will be used for higher quality quantization.
Otherwise falls back to onnxruntime.quantization.
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
from loguru import logger


def _load_calibration_images(
    calibration_dir: Path,
    num_samples: int = 100,
    input_size: tuple[int, int] = (224, 224),
) -> list[np.ndarray]:
    """Load and preprocess sample images for calibration."""
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = []

    for fpath in sorted(calibration_dir.rglob("*")):
        if fpath.suffix.lower() not in extensions:
            continue
        img = cv2.imread(str(fpath))
        if img is None:
            continue

        img = cv2.resize(img, input_size)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0

        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std
        img = np.transpose(img, (2, 0, 1))
        images.append(np.expand_dims(img, axis=0))

        if len(images) >= num_samples:
            break

    logger.info("Loaded {} calibration images", len(images))
    return images


class NumpyCalibrationDataReader:
    """Calibration data reader for onnxruntime quantization."""

    def __init__(self, images: list[np.ndarray], input_name: str = "input") -> None:
        self.images = images
        self.input_name = input_name
        self.idx = 0

    def get_next(self) -> dict | None:
        if self.idx >= len(self.images):
            return None
        data = {self.input_name: self.images[self.idx]}
        self.idx += 1
        return data

    def rewind(self) -> None:
        self.idx = 0


def quantize_with_onnxruntime(
    input_model: Path,
    output_model: Path,
    calibration_images: list[np.ndarray],
    input_name: str = "input",
) -> None:
    """Quantize model using onnxruntime's static quantizer."""
    from onnxruntime.quantization import (
        CalibrationMethod,
        QuantFormat,
        QuantType,
        quantize_static,
    )

    logger.info("Quantizing with onnxruntime (static INT8)...")
    calibration_reader = NumpyCalibrationDataReader(calibration_images, input_name)

    quantize_static(
        model_input=str(input_model),
        model_output=str(output_model),
        calibration_data_reader=calibration_reader,
        quant_format=QuantFormat.QDQ,  # QDQ format for Vitis AI compatibility
        per_channel=False,
        weight_type=QuantType.QInt8,
        activation_type=QuantType.QInt8,
        calibrate_method=CalibrationMethod.MinMax,
    )
    logger.info("Quantized model saved to {}", output_model)


def quantize_with_quark(
    input_model: Path,
    output_model: Path,
    calibration_images: list[np.ndarray],
    input_name: str = "input",
) -> None:
    """Quantize model using AMD Quark (higher quality, recommended)."""
    try:
        from quark.onnx import ModelQuantizer
        from quark.onnx.quantization.config import Config, QuantizationConfig
    except ImportError:
        raise ImportError(
            "AMD Quark not installed. Install with: pip install amd-quark"
        )

    logger.info("Quantizing with AMD Quark (INT8, Xint8 for Vitis AI)...")

    quant_config = QuantizationConfig(
        quant_format="QDQ",
        calibrate_method="MinMax",
        activation_type="QInt8",
        weight_type="QInt8",
        enable_npu_cnn=True,  # Optimize for NPU CNN workloads
    )

    config = Config(global_quant_config=quant_config)
    calibration_reader = NumpyCalibrationDataReader(calibration_images, input_name)

    quantizer = ModelQuantizer(config)
    quantizer.quantize_model(
        str(input_model),
        str(output_model),
        calibration_reader,
    )
    logger.info("Quark quantized model saved to {}", output_model)


def quantize_model(
    input_model: Path,
    output_model: Path,
    calibration_dir: Path,
    num_samples: int = 100,
    prefer_quark: bool = True,
) -> Path:
    """Quantize an ONNX model for AMD NPU deployment.

    Tries AMD Quark first (if installed), falls back to onnxruntime quantizer.

    Returns:
        Path to the quantized model.
    """
    import onnxruntime as ort

    # Get input name from the model
    sess = ort.InferenceSession(str(input_model), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    del sess

    calibration_images = _load_calibration_images(calibration_dir, num_samples)
    if not calibration_images:
        raise ValueError(f"No calibration images found in {calibration_dir}")

    output_model.parent.mkdir(parents=True, exist_ok=True)

    if prefer_quark:
        try:
            quantize_with_quark(
                input_model, output_model, calibration_images, input_name
            )
            return output_model
        except ImportError:
            logger.info("AMD Quark not available, falling back to onnxruntime quantizer")

    try:
        quantize_with_onnxruntime(
            input_model, output_model, calibration_images, input_name
        )
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"{e}. Install with: pip install onnx>=1.16.0"
        ) from e
    return output_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Quantize ONNX model for AMD NPU")
    parser.add_argument("--input", type=Path, required=True, help="Input FP32 ONNX model")
    parser.add_argument("--output", type=Path, required=True, help="Output INT8 ONNX model")
    parser.add_argument(
        "--calibration-dir",
        type=Path,
        required=True,
        help="Directory with sample images for calibration",
    )
    parser.add_argument("--num-samples", type=int, default=100)
    parser.add_argument("--no-quark", action="store_true", help="Skip AMD Quark, use onnxruntime")
    args = parser.parse_args()

    quantize_model(
        args.input,
        args.output,
        args.calibration_dir,
        args.num_samples,
        prefer_quark=not args.no_quark,
    )


if __name__ == "__main__":
    main()
