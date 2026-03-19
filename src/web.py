"""Web UI for Photo Metadata Extractor."""

import csv
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import urllib.parse

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from src.config import AppConfig
from src.csv_writer import build_record, load_existing_records, save_records
from src.models.content_classifier import auto_quantize, needs_quantization
from src.pipeline import ProcessingPipeline
from src.scanner import scan_directory

app = FastAPI(title="Photo Metadata Extractor")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["urlencode"] = urllib.parse.quote

# ── Extraction state ──────────────────────────────────────────────────────────

_lock = threading.Lock()
_stop_event = threading.Event()
_state: dict = {
    "running": False,
    "logs": [],
    "progress": 0,
    "total": 0,
    "error": None,
    "start_time": None,
    "stats": None,
    "stopped": False,
}


def _log_sink(message) -> None:
    record = message.record
    extra = record["extra"]
    entry: dict = {
        "time": record["time"].strftime("%H:%M:%S"),
        "level": record["level"].name,
        "text": record["message"],
    }
    if "log_key" in extra:
        entry["key"] = extra["log_key"]
        entry["params"] = extra.get("log_params", {})
    with _lock:
        _state["logs"].append(entry)
        if len(_state["logs"]) > 1000:
            _state["logs"] = _state["logs"][-1000:]


def _run_extraction(root_dir: str, skip_existing: bool, num_colors: int, max_workers: int = 4, execution_provider: str = "CPUExecutionProvider") -> None:
    _stop_event.clear()
    with _lock:
        _state.update({
            "running": True,
            "logs": [],
            "progress": 0,
            "total": 0,
            "error": None,
            "start_time": time.monotonic(),
            "stats": None,
            "stopped": False,
        })

    sink_id = logger.add(_log_sink, format="{message}", level="INFO")
    try:
        config = AppConfig(
            root_dir=root_dir,
            skip_existing=skip_existing,
            num_colors=num_colors,
            max_workers=max_workers,
            execution_provider=execution_provider,
        )

        # Store CSV in the scanned directory; record location in /data/.pme_last_scan
        csv_path = Path(root_dir) / config.csv_filename

        scans = scan_directory(config)
        if not scans:
            logger.bind(log_key="log.no_images").info("No images found.")
            return

        existing = load_existing_records(csv_path) if skip_existing else {}

        to_process = []
        for scan in scans:
            abs_path = str(scan.path)
            if (
                abs_path in existing
                and scan.updated_at <= existing[abs_path].last_processing_date
            ):
                continue
            to_process.append(scan)

        with _lock:
            _state["total"] = len(to_process)

        logger.bind(
            log_key="log.found",
            log_params={"n": len(scans), "m": len(to_process)},
        ).info("Found {} images, to process: {}", len(scans), len(to_process))

        if not to_process:
            logger.bind(log_key="log.nothing_to_do").info("Nothing to process. CSV is up to date.")
            return

        # ── Auto-quantize for AMD NPU if INT8 model is missing ────────────────
        fp32_path = Path(config.model_cache_dir) / "mobilenetv2-12.onnx"
        int8_path = Path(config.model_cache_dir) / "mobilenetv2-12-int8.onnx"
        if needs_quantization(fp32_path, int8_path, execution_provider):
            n = min(100, len(to_process))
            logger.bind(log_key="log.quantize_start", log_params={"n": n}).info(
                "AMD NPU detected — auto-creating INT8 model from {} sample images…", n
            )
            ok = auto_quantize(fp32_path, int8_path, [s.path for s in to_process], num_samples=100)
            if ok:
                logger.bind(log_key="log.quantize_done").info(
                    "INT8 model ready — processing will use the NPU."
                )
            else:
                logger.bind(log_key="log.quantize_failed").warning(
                    "Auto-quantization failed, falling back to FP32 on CPU."
                )
        # ──────────────────────────────────────────────────────────────────────

        thread_local = threading.local()
        _worker_pipelines: list = []
        _workers_lock = threading.Lock()

        def _init_worker():
            p = ProcessingPipeline(config)
            thread_local.pipeline = p
            with _workers_lock:
                _worker_pipelines.append(p)

        def _process(scan):
            return thread_local.pipeline.process_image(scan)

        next_id = max((r.id for r in existing.values()), default=0) + 1
        all_records = dict(existing)
        processed = 0
        _proc_lock = threading.Lock()

        user_stopped = False
        executor = ThreadPoolExecutor(max_workers=config.max_workers,
                                     initializer=_init_worker)
        try:
            futures = {executor.submit(_process, scan): scan for scan in to_process}

            for future in as_completed(futures):
                if _stop_event.is_set():
                    user_stopped = True
                    break

                scan = futures[future]
                try:
                    metadata = future.result()
                except Exception as exc:
                    logger.warning("Unexpected error processing {}: {}", scan.file_name, exc)
                    metadata = None

                abs_path = str(scan.path)

                if metadata is not None:
                    with _proc_lock:
                        record_id = existing[abs_path].id if abs_path in existing else next_id
                        if abs_path not in existing:
                            next_id += 1
                        all_records[abs_path] = build_record(
                            record_id=record_id,
                            file_name=scan.file_name,
                            absolute_path=abs_path,
                            file_extension=scan.extension,
                            created_at=scan.created_at,
                            updated_at=scan.updated_at,
                            metadata=metadata,
                        )
                        processed += 1
                        should_save = processed % config.batch_size == 0
                        snapshot = list(all_records.values()) if should_save else None

                    if should_save:
                        save_records(csv_path, snapshot)

                with _lock:
                    _state["progress"] += 1
        finally:
            if user_stopped:
                executor.shutdown(wait=False, cancel_futures=True)
            else:
                executor.shutdown(wait=True)
            for p in _worker_pipelines:
                try:
                    p.close()
                except Exception:
                    pass

        save_records(csv_path, list(all_records.values()))
        Path("/data/.pme_last_scan").write_text(str(csv_path), encoding="utf-8")

        if user_stopped:
            logger.bind(log_key="log.stopped").warning("Processing stopped by user")
            with _lock:
                _state["stopped"] = True
        else:
            elapsed = time.monotonic() - _state["start_time"]
            logger.bind(
                log_key="log.done",
                log_params={"n": processed, "s": f"{elapsed:.1f}"},
            ).info("Done! Processed {} images in {:.1f}s", processed, elapsed)

            with _lock:
                _state["stats"] = {"processed": processed, "elapsed": round(elapsed, 1)}

    except Exception as e:
        logger.bind(log_key="log.extract_error", log_params={"e": str(e)}).error(
            "Extraction error: {}", e
        )
        with _lock:
            _state["error"] = str(e)
    finally:
        logger.remove(sink_id)
        with _lock:
            _state["running"] = False


# ── Pages ─────────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/photo/{photo_id}", response_class=HTMLResponse)
async def photo_page(request: Request, photo_id: int, dir: str | None = Query(default=None)):
    photos = _read_csv(dir)
    photo = next((p for p in photos if p["id"] == photo_id), None)
    if photo is None:
        raise HTTPException(404, "Фото не найдено")
    return templates.TemplateResponse("photo.html", {"request": request, "photo": photo, "dir": dir or ""})


# ── API ───────────────────────────────────────────────────────────────────────


@app.get("/api/photos")
async def get_photos(dir: str | None = None):
    return JSONResponse(_read_csv(dir))


@app.get("/api/photo/{photo_id}")
async def get_photo(photo_id: int):
    photos = _read_csv()
    photo = next((p for p in photos if p["id"] == photo_id), None)
    if photo is None:
        raise HTTPException(404, "Фото не найдено")
    return JSONResponse(photo)


@app.get("/api/image/{photo_id}")
async def serve_image(photo_id: int, dir: str | None = Query(default=None)):
    photos = _read_csv(dir)
    photo = next((p for p in photos if p["id"] == photo_id), None)
    if photo is None:
        raise HTTPException(404, "Фото не найдено")
    abs_path = Path(photo["absolute_path"]).resolve()
    allowed_roots = [Path("/data").resolve()]
    if not any(str(abs_path).startswith(str(r)) for r in allowed_roots):
        raise HTTPException(403, "Доступ запрещён")
    if not abs_path.exists():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(abs_path)


@app.post("/api/run")
async def run_extraction(body: dict):
    with _lock:
        if _state["running"]:
            return JSONResponse({"error": "Обработка уже запущена"}, status_code=409)

    root_dir = body.get("root_dir", os.environ.get("PME_ROOT_DIR", "/data"))
    skip_existing = body.get("skip_existing", True)
    num_colors = int(body.get("num_colors", os.environ.get("PME_NUM_COLORS", "5")))
    max_workers = int(body.get("max_workers", os.environ.get("PME_MAX_WORKERS", "4")))
    execution_provider = body.get("execution_provider", os.environ.get("PME_EXECUTION_PROVIDER", "CPUExecutionProvider"))

    t = threading.Thread(
        target=_run_extraction,
        args=(root_dir, skip_existing, num_colors, max_workers, execution_provider),
        daemon=True,
    )
    t.start()
    return JSONResponse({"status": "started"})


@app.get("/api/status")
async def get_status():
    with _lock:
        return JSONResponse(dict(_state))


@app.post("/api/stop")
async def stop_extraction():
    with _lock:
        if not _state["running"]:
            return JSONResponse({"error": "Not running"}, status_code=409)
    _stop_event.set()
    return JSONResponse({"status": "stopping"})


@app.get("/api/browse")
async def browse(path: str = "/data"):
    data_root = Path("/data").resolve()
    abs_path = Path(path).resolve()

    # Allow browsing only within /data
    if not str(abs_path).startswith(str(data_root)):
        abs_path = data_root
    if not abs_path.exists() or not abs_path.is_dir():
        raise HTTPException(404, "Директория не найдена")

    dirs = []
    try:
        for item in sorted(abs_path.iterdir(), key=lambda p: p.name.lower()):
            if item.is_dir() and not item.name.startswith("."):
                dirs.append({"name": item.name, "path": str(item)})
    except PermissionError:
        pass

    parent = str(abs_path.parent) if abs_path != data_root else None
    return JSONResponse({"path": str(abs_path), "parent": parent, "dirs": dirs})


@app.get("/api/config")
async def get_config():
    import multiprocessing
    return JSONResponse({
        "root_dir": os.environ.get("PME_ROOT_DIR", "/data"),
        "execution_provider": os.environ.get("PME_EXECUTION_PROVIDER", "CPUExecutionProvider"),
        "num_colors": int(os.environ.get("PME_NUM_COLORS", "5")),
        "skip_existing": os.environ.get("PME_SKIP_EXISTING", "true").lower() == "true",
        "max_workers": int(os.environ.get("PME_MAX_WORKERS", "4")),
        "cpu_count": multiprocessing.cpu_count(),
    })


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read_csv(root_dir: str | None = None) -> list[dict]:
    csv_filename = os.environ.get("PME_CSV_FILENAME", "photo_metadata.csv")
    if root_dir:
        csv_path = Path(root_dir) / csv_filename
    else:
        last_scan = Path("/data/.pme_last_scan")
        if last_scan.exists():
            csv_path = Path(last_scan.read_text(encoding="utf-8").strip())
        else:
            csv_path = Path(os.environ.get("PME_ROOT_DIR", "/data")) / csv_filename

    if not csv_path.exists():
        return []

    photos = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    meta = json.loads(row.get("metadata", "{}"))
                except json.JSONDecodeError:
                    meta = {}
                photos.append({
                    "id": int(row.get("id", 0)),
                    "file_name": row.get("file_name", ""),
                    "absolute_path": row.get("absolute_path", ""),
                    "file_extension": row.get("file_extension", ""),
                    "created_at": row.get("created_at", ""),
                    "updated_at": row.get("updated_at", ""),
                    "last_processing_date": row.get("last_processing_date", ""),
                    "width": meta.get("width", 0),
                    "height": meta.get("height", 0),
                    "categories": meta.get("content_categories", []),
                    "scores": meta.get("content_scores", {}),
                    "colors": meta.get("dominant_colors", []),
                })
    except Exception as e:
        logger.error(f"Ошибка чтения CSV: {e}")

    return photos


if __name__ == "__main__":
    uvicorn.run("src.web:app", host="0.0.0.0", port=8080, reload=False)
