# Photo Metadata Extractor

Рекурсивно сканирует директорию с фотографиями, извлекает метаданные с помощью ML-моделей (с ускорением на NPU) и сохраняет результат в CSV.

## Что извлекается

| Метаданные | Модель / метод | Устройство |
|---|---|---|
| Категория контента (город, природа, портрет, архитектура, еда, ...) | MobileNetV2 (ONNX) → маппинг ImageNet→категории | NPU / GPU / CPU |
| Доминантные цвета (3-5 штук с HEX, именем, %) | Mini-Batch K-Means кластеризация | CPU |
| Размеры (width × height) | OpenCV | CPU |

## Структура CSV

```
id, file_name, absolute_path, file_extension, created_at, updated_at, last_processing_date, metadata
```

Поле `metadata` — JSON с полной структурой:
```json
{
  "content_categories": ["nature", "animal"],
  "content_scores": {"nature": 0.72, "animal": 0.15},
  "dominant_colors": [
    {"hex": "#4A7C2E", "name": "darkolivegreen", "percentage": 35.2},
    {"hex": "#87CEEB", "name": "skyblue", "percentage": 28.1}
  ],
  "width": 4032,
  "height": 3024
}
```

## Быстрый старт

### Docker (рекомендуется)

```bash
# Клонировать и настроить
cp .env.example .env
# Отредактировать .env — указать PHOTOS_DIR

# Запустить
PHOTOS_DIR=/path/to/photos docker compose up --build
```

### NPU Device Passthrough

Для Intel NPU (Meteor Lake+) убедитесь, что:

1. Установлен NPU-драйвер в хост-системе:
   ```bash
   # Проверить наличие устройства
   ls /dev/accel/
   ```

2. В `docker-compose.yml` раскомментирована секция `devices`:
   ```yaml
   devices:
     - /dev/accel:/dev/accel
   ```

3. Если NPU недоступен — приложение автоматически откатится на CPU.

### Локальный запуск (без Docker)

```bash
# Установить зависимости
pip install -e .

# Запустить
python -m src.main --root-dir /path/to/photos

# Или через env
PME_ROOT_DIR=/path/to/photos python -m src.main
```

## CLI параметры

```
--root-dir PATH       Корневая директория с фотографиями
--csv-filename NAME   Имя CSV файла (default: photo_metadata.csv)
--npu-device DEVICE   NPU | GPU | CPU (default: NPU)
--no-skip             Переобработать все файлы
--num-colors N        Кол-во доминантных цветов (default: 5)
```

## Переменные окружения

Все параметры можно задать через env-переменные с префиксом `PME_`:

| Переменная | Описание | Default |
|---|---|---|
| `PME_ROOT_DIR` | Корневая директория | (обязательно) |
| `PME_CSV_FILENAME` | Имя CSV | `photo_metadata.csv` |
| `PME_NPU_DEVICE` | Устройство OpenVINO | `NPU` |
| `PME_SKIP_EXISTING` | Пропуск обработанных | `true` |
| `PME_NUM_COLORS` | Кол-во цветов | `5` |
| `PME_BATCH_SIZE` | Размер батча | `16` |
| `PME_CONFIDENCE_THRESHOLD` | Мин. уверенность категории | `0.05` |

## Инкрементальная обработка

По умолчанию приложение:
- Читает существующий CSV
- Пропускает файлы, которые уже обработаны и не изменились
- Переобрабатывает файлы, которые были модифицированы после последней обработки
- Добавляет новые файлы

Для полной переобработки: `--no-skip` или `PME_SKIP_EXISTING=false`.

## Архитектура

```
src/
├── main.py                 # CLI entry point
├── config.py               # Pydantic Settings конфигурация
├── scanner.py              # Рекурсивный скан директорий
├── pipeline.py             # Оркестрация моделей
├── csv_writer.py           # CSV чтение/запись
├── schemas.py              # Pydantic-модели данных
└── models/
    ├── base.py             # Базовый класс ONNX + NPU fallback
    ├── content_classifier.py   # MobileNetV2 классификатор
    └── color_extractor.py      # K-Means доминантные цвета
```

## Поддерживаемые форматы

`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp`

## Добавление новых моделей

1. Создать класс, наследующий `BaseONNXModel` в `src/models/`
2. Реализовать `preprocess()` и `predict()`
3. Подключить в `ProcessingPipeline.__init__()` и `process_image()`
4. Расширить `ImageMetadata` в `schemas.py`

Базовый класс автоматически обеспечит NPU→GPU→CPU fallback.
