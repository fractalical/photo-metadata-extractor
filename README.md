# Photo Metadata Extractor

Recursively scans a photo directory, extracts metadata using ML models (with optional NPU acceleration), and saves results to CSV. Includes a web UI for managing runs and browsing results.

## What Gets Extracted

| Metadata | Method | Device |
|---|---|---|
| Content category (portrait, nature, food, architecture, vehicle…) | MobileNetV2 (ONNX) + face detection | NPU / GPU / CPU |
| Dominant colors (3–5 with HEX, name, %) | Mini-Batch K-Means clustering | CPU |
| Dimensions (width × height) | OpenCV | CPU |

## Quick Start

Download one script for your OS and run it — no git clone needed.

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/fractalical/photo-metadata-extractor/main/start.sh -o start.sh
chmod +x start.sh && ./start.sh
```

**Windows (PowerShell):**
```powershell
Invoke-WebRequest https://raw.githubusercontent.com/fractalical/photo-metadata-extractor/main/start.ps1 -OutFile start.ps1
.\start.ps1
```

**Windows (CMD):** download [start.bat](https://raw.githubusercontent.com/fractalical/photo-metadata-extractor/main/start.bat) and double-click it.

The script pulls the pre-built Docker image (~500 MB on first run, cached after that) and opens the UI at **http://localhost:8080**.

> **Requires:** [Docker](https://docs.docker.com/get-docker/) installed and running.

## Web UI

| Tab | What it does |
|-----|-------------|
| **Run** | Browse & select folder, configure options, start extraction, watch live logs |
| **Photos** | Search and filter processed photos, view color swatches and categories |
| **Photo detail** | Full image + all metadata (click any row) |

## CSV Structure

```
id, file_name, absolute_path, file_extension, created_at, updated_at, last_processing_date, metadata
```

The `metadata` field is a JSON string:
```json
{
  "content_categories": ["portrait", "nature"],
  "content_scores": {"portrait": 0.82, "nature": 0.15},
  "dominant_colors": [
    {"hex": "#4A7C2E", "name": "darkolivegreen", "percentage": 35.2},
    {"hex": "#87CEEB", "name": "skyblue", "percentage": 28.1}
  ],
  "width": 4032,
  "height": 3024
}
```

## Environment Variables

All parameters use the `PME_` prefix and can be set in `.env`:

| Variable | Description | Default |
|---|---|---|
| `PHOTOS_DIR` | Host path to photos folder | `./photos` |
| `BROWSE_ROOT` | Host path shown in the folder browser | `/home` (Linux) / `C:\Users` (Windows) |
| `PORT` | Web UI port | `8080` |
| `PME_ROOT_DIR` | Photos path inside container | `/data` |
| `PME_CSV_FILENAME` | Output CSV filename | `photo_metadata.csv` |
| `PME_NPU_DEVICE` | OpenVINO device: NPU / GPU / CPU | `NPU` |
| `PME_SKIP_EXISTING` | Skip already-processed files | `true` |
| `PME_NUM_COLORS` | Number of dominant colors to extract | `5` |
| `PME_BATCH_SIZE` | Processing batch size | `16` |
| `PME_CONFIDENCE_THRESHOLD` | Min confidence to show a category | `0.12` |

## Platform Support

| Platform | Status | Notes |
|---|---|---|
| Linux (x86_64) | ✅ Full support | Default, recommended |
| macOS (Intel / Apple Silicon) | ✅ Works | CPU mode only |
| Windows 10/11 | ✅ Works | Requires Docker Desktop + WSL2 |
| Intel NPU (Meteor Lake / Arrow Lake) | ✅ Supported | Use `--profile intel` |
| AMD Ryzen AI (7040 / 8040 series) | ⚠️ Experimental | Requires Vitis AI on host |
| CPU (any hardware) | ✅ Default | No configuration needed |

See [`docs/`](docs/) for platform-specific setup guides.

**User guides:**
- [English guide](docs/guide-en.md) — full usage instructions with examples
- [Руководство на русском](docs/guide-ru.md) — полная инструкция с примерами

## NPU Profiles (CLI, advanced)

```bash
# Intel NPU via OpenVINO
docker compose --profile intel up --build

# AMD Ryzen AI XDNA NPU (requires host Vitis AI runtime)
docker compose --profile amd up --build
```

### Intel NPU requirements
1. Install NPU driver on the host
2. Verify device: `ls /dev/accel/`
3. If unavailable, the app falls back to CPU automatically

### Model quantization for AMD NPU (INT8)
```bash
python -m src.models.quantize \
    --input models/mobilenetv2-12.onnx \
    --output models/mobilenetv2-12-int8.onnx \
    --calibration-dir /path/to/sample/images
```

## Incremental Processing

By default the app:
- Reads the existing CSV
- Skips files already processed and unchanged
- Re-processes files modified after last run
- Appends new files

To re-process everything: uncheck **Skip already processed** in the UI, or use `PME_SKIP_EXISTING=false`.

## Local Development (without Docker)

```bash
pip install -e ".[dev]"
python -m src.main --root-dir /path/to/photos

# Or via web UI locally
pip install -e ".[web]"
uvicorn src.web:app --host 0.0.0.0 --port 8080
```

## Architecture

```
src/
├── main.py                  # CLI entry point
├── web.py                   # FastAPI web UI
├── config.py                # Pydantic Settings
├── scanner.py               # Recursive directory scanner
├── pipeline.py              # Model orchestration + face detection
├── csv_writer.py            # CSV read/write
├── schemas.py               # Pydantic data models
├── templates/               # Jinja2 HTML templates
│   ├── index.html
│   └── photo.html
└── models/
    ├── base.py              # Base ONNX class + NPU fallback
    ├── content_classifier.py    # MobileNetV2 classifier
    ├── color_extractor.py       # K-Means dominant colors
    └── quantize.py              # INT8 quantization for AMD NPU
```

## Supported Formats

`.jpg` `.jpeg` `.png` `.bmp` `.tiff` `.tif` `.webp`

## Extending with New Models

1. Create a class extending `BaseONNXModel` in `src/models/`
2. Implement `preprocess()` and `predict()`
3. Wire it into `ProcessingPipeline.__init__()` and `process_image()`
4. Extend `ImageMetadata` in `schemas.py`

The base class handles NPU → GPU → CPU fallback automatically.
