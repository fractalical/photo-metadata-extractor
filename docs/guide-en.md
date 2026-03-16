# Photo Metadata Extractor — User Guide

A tool that automatically analyzes your photo library: it detects what's in each photo, extracts the dominant colors, and saves everything to a spreadsheet you can open in Excel or Google Sheets.

---

## What you need

- **Docker Desktop** — free software that runs the app in an isolated container (no Python or anything else needed)
  - [Download for Windows](https://www.docker.com/products/docker-desktop/)
  - [Download for Mac](https://www.docker.com/products/docker-desktop/)
  - On Ubuntu/Debian Linux: `sudo apt install docker.io docker-compose-plugin`

- About **500 MB of free disk space** (for the app image and AI model)
- An internet connection for the first launch (to download the model, ~14 MB)

---

## Installation

1. Download or clone this project to your computer
2. That's it — no other installation is needed

---

## First launch

### Windows

Double-click **`start.bat`**, or right-click **`start.ps1`** → *Run with PowerShell*.

### Linux / macOS

Open a terminal in the project folder and run:
```bash
./start.sh
```

### What happens next

The script will ask two questions:

1. **Photos directory** — the folder containing your photos (e.g. `C:\Users\Anna\Pictures` or `/home/anna/Pictures`). Press Enter to use the default.
2. **Port** — just press Enter (uses 8080 by default).

On the **first launch**, Docker builds the app image — this takes **2–5 minutes**. Subsequent launches take only a few seconds.

When you see `Application startup complete`, open your browser and go to:

**http://localhost:8080**

---

## Examples

See [examples.md](examples-en.md) for a visual walkthrough of the app with annotated screenshots.

---

## Using the web interface

### Tab: Run

This is where you start processing your photos.

**Configuration** (top section) — shows the current settings read from your environment.

**Run parameters:**
- **Scan directory** — click the folder icon or the field to open the folder browser. Navigate to the folder with your photos and click **Select**.
- **Colors** — how many dominant colors to extract per photo (default: 5).
- **Skip already processed** — checked by default. Only new or changed photos will be processed. Uncheck to re-analyze everything.

Click **Run** to start. You will see:
- A progress bar showing how many photos have been processed
- Live logs in the terminal-style panel below

Processing speed on CPU: roughly **30–60 photos per second** for color extraction. Content classification takes a bit longer.

---

### Tab: Photos

After processing, switch to the **Photos** tab to see results.

**Search** — type a filename or category name (e.g. `portrait`, `nature`, `food`) to filter the list.

**Table columns:**
| Column | Description |
|--------|-------------|
| # | Internal ID |
| Name | Filename |
| Resolution | Width × Height in pixels |
| Categories | What the AI detected in the photo |
| Colors | Dominant colors as small swatches |
| Processed | Date when the photo was analyzed |

**Click any row** to open the photo detail page in a new browser tab.

---

### Photo detail page

Shows the photo on the left and all extracted metadata on the right:

- **File information** — name, resolution, format, path, dates
- **Content categories** — what the AI detected, with a confidence bar. Higher bar = more confident.
- **Dominant colors** — color swatches with CSS color names, HEX codes, and percentage of the image area

---

## Understanding the results

### Content categories

The AI model (MobileNetV2) was trained to recognize objects from a list of 1000 categories. These are mapped to 11 groups:

| Category | Examples of what it detects |
|----------|-----------------------------|
| `portrait` | Photos with human faces |
| `animal` | Dogs, cats, birds, fish, insects… |
| `nature` | Mountains, lakes, forests, flowers, beaches… |
| `food` | Pizza, fruit, coffee, plates of food… |
| `vehicle` | Cars, motorcycles, planes, boats… |
| `architecture` | Churches, castles, bridges, towers… |
| `city` | Streets, traffic, crosswalks… |
| `indoor` | Furniture, monitors, appliances… |
| `sport` | Balls, rackets, skis, surfboards… |
| `document` | Books, newspapers, notebooks… |
| `other` | Everything that doesn't fit the above |

> **Note:** This model works best for clearly visible objects. Artistic photos, abstract backgrounds, or unusual angles may result in low-confidence or `other` classifications.

### Dominant colors

Colors are extracted by clustering pixel values with K-Means. Each color shows:
- A color swatch
- The closest **CSS color name** (e.g. "Darkolivegreen", "Sienna")
- The **HEX code** (e.g. `#4A7C2E`) — usable in any design tool
- The **percentage** of the total image area

---

## Output file

After processing, a file named **`photo_metadata.csv`** is saved in your photos folder. You can open it in:
- Microsoft Excel
- Google Sheets (File → Import)
- LibreOffice Calc
- Any database or script

Each row is one photo. The `metadata` column contains a JSON string with the full details.

---

## Stopping the app

Press **Ctrl+C** in the terminal window where the app is running.

To start again later, just run `start.sh` / `start.bat` again — it will be fast since the image is already built.

---

## Troubleshooting

**The page doesn't open at http://localhost:8080**
- Make sure Docker is running
- Wait a few more seconds — the app may still be starting
- Check that port 8080 is not used by another application (change `PORT=8081` in `.env`)

**"Docker is not running" error**
- Open Docker Desktop and wait until the whale icon in the taskbar stops animating

**Photos are not showing in the folder browser**
- The browser only shows subfolders of the configured root. If your photos are on a different drive (Windows), edit `BROWSE_ROOT` in `.env`

**Processing is very slow**
- On CPU, large photos (20+ MP) are slower. Consider resizing to ≤ 8 MP for faster analysis
- A folder with 1000 photos typically takes 30–60 seconds

**Categories look wrong**
- The model may not handle unusual subjects well — this is a known limitation of ImageNet-based classifiers
- Portrait detection uses face recognition and is generally reliable for human photos
