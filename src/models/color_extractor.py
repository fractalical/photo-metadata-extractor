"""Dominant color extraction using K-Means clustering.

This doesn't require NPU — it's a lightweight algorithm.
Uses mini-batch K-Means on downsampled pixels for speed.
"""

import cv2
import numpy as np
import webcolors
from sklearn.cluster import MiniBatchKMeans

from src.schemas import DominantColor


def _closest_color_name(hex_color: str) -> str:
    """Find the closest CSS3 named color."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    min_dist = float("inf")
    closest = "unknown"

    for name in webcolors.names("css3"):
        hex_val = webcolors.name_to_hex(name, spec="css3")
        cr, cg, cb = int(hex_val[1:3], 16), int(hex_val[3:5], 16), int(hex_val[5:7], 16)
        dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if dist < min_dist:
            min_dist = dist
            closest = name

    return closest


class ColorExtractor:
    """Extract dominant colors from an image using K-Means."""

    def __init__(self, num_colors: int = 5, sample_size: int = 10_000) -> None:
        self.num_colors = num_colors
        self.sample_size = sample_size

    def extract(self, image: np.ndarray) -> list[DominantColor]:
        """Extract dominant colors from a BGR image.

        Args:
            image: BGR image from cv2.imread.

        Returns:
            List of DominantColor sorted by percentage descending.
        """
        # Convert to RGB
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Reshape to pixel array
        pixels = img_rgb.reshape(-1, 3).astype(np.float32)

        # Subsample for speed
        if len(pixels) > self.sample_size:
            indices = np.random.default_rng(42).choice(
                len(pixels), self.sample_size, replace=False
            )
            pixels = pixels[indices]

        # K-Means clustering
        n_clusters = min(self.num_colors, len(pixels))
        kmeans = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=42,
            batch_size=min(1000, len(pixels)),
            n_init=3,
        )
        labels = kmeans.fit_predict(pixels)
        centers = kmeans.cluster_centers_

        # Count pixels per cluster → percentage
        unique, counts = np.unique(labels, return_counts=True)
        total = counts.sum()

        colors: list[DominantColor] = []
        for cluster_idx, count in zip(unique, counts):
            r, g, b = centers[cluster_idx].astype(int)
            hex_code = f"#{r:02X}{g:02X}{b:02X}"
            colors.append(
                DominantColor(
                    hex=hex_code,
                    name=_closest_color_name(hex_code),
                    percentage=round(count / total * 100, 1),
                )
            )

        colors.sort(key=lambda c: -c.percentage)
        return colors
