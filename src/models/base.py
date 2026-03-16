"""Base class for ONNX Runtime models with multi-vendor NPU support.

Supports:
  - Intel NPU via OpenVINOExecutionProvider
  - AMD XDNA NPU via VitisAIExecutionProvider (requires quantized INT8/BF16 models)
  - CPU fallback via CPUExecutionProvider
"""

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import onnxruntime as ort
from loguru import logger


def get_available_providers() -> list[str]:
    """Return list of available ONNX Runtime execution providers."""
    return ort.get_available_providers()


def detect_npu_vendor() -> str:
    """Auto-detect NPU vendor from available providers.

    Returns:
        'intel' if OpenVINO EP available,
        'amd' if VitisAI EP available,
        'cpu' otherwise.
    """
    available = get_available_providers()
    if "VitisAIExecutionProvider" in available:
        return "amd"
    if "OpenVINOExecutionProvider" in available:
        return "intel"
    return "cpu"


class BaseONNXModel(ABC):
    """Base class handling ONNX Runtime session with multi-vendor NPU fallback.

    Provider chain:
      AMD:   VitisAI (NPU) → CPUExecutionProvider
      Intel: OpenVINO (NPU) → OpenVINO (GPU) → OpenVINO (CPU) → CPUExecutionProvider
      CPU:   CPUExecutionProvider
    """

    def __init__(
        self,
        model_path: Path,
        execution_provider: str = "auto",
        npu_device: str = "NPU",
        vitis_config: Path | None = None,
    ) -> None:
        self.model_path = model_path
        self.vitis_config = vitis_config
        self.session = self._create_session(execution_provider, npu_device)
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape

        active_provider = self.session.get_providers()[0]
        logger.info(
            "Model {} loaded | provider: {} | device: {}",
            model_path.name,
            active_provider,
            npu_device if active_provider != "CPUExecutionProvider" else "CPU",
        )

    def _create_session(
        self, execution_provider: str, npu_device: str
    ) -> ort.InferenceSession:
        """Create ONNX session with graceful fallback chain."""
        providers_to_try: list[tuple[str, dict]] = []

        # Auto-detect vendor if 'auto'
        if execution_provider == "auto":
            vendor = detect_npu_vendor()
            if vendor == "amd":
                execution_provider = "VitisAIExecutionProvider"
            elif vendor == "intel":
                execution_provider = "OpenVINOExecutionProvider"
            else:
                execution_provider = "CPUExecutionProvider"
            logger.info("Auto-detected NPU vendor: {} → {}", vendor, execution_provider)

        if execution_provider == "VitisAIExecutionProvider":
            # AMD XDNA NPU via Vitis AI
            vitis_opts: dict = {}
            if self.vitis_config and self.vitis_config.exists():
                vitis_opts["config_file"] = str(self.vitis_config)
            providers_to_try.append(("VitisAIExecutionProvider", vitis_opts))

        elif execution_provider == "OpenVINOExecutionProvider":
            # Intel NPU → GPU → CPU via OpenVINO
            for device in [npu_device, "GPU", "CPU"]:
                providers_to_try.append(
                    (
                        "OpenVINOExecutionProvider",
                        {"device_type": device, "precision": "FP16"},
                    )
                )

        # Always add CPU as final fallback
        providers_to_try.append(("CPUExecutionProvider", {}))

        for provider, options in providers_to_try:
            try:
                sess_options = ort.SessionOptions()
                sess_options.graph_optimization_level = (
                    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                )
                session = ort.InferenceSession(
                    str(self.model_path),
                    sess_options=sess_options,
                    providers=(
                        [(provider, options)] if options else [provider]
                    ),
                )
                device_info = options.get("device_type", "NPU") if options else "CPU"
                logger.debug("Session created with {} ({})", provider, device_info)
                return session
            except Exception as e:
                device_info = options.get("device_type", "CPU") if options else "CPU"
                logger.warning(
                    "Failed to init {} ({}): {}. Trying next...",
                    provider,
                    device_info,
                    e,
                )

        raise RuntimeError("No ONNX execution provider available")

    @abstractmethod
    def predict(self, image: np.ndarray) -> dict:
        """Run inference on a preprocessed image."""
        ...

    def predict_batch(self, images: list[np.ndarray]) -> list[dict]:
        """Run inference on a batch. Default: sequential."""
        return [self.predict(img) for img in images]
