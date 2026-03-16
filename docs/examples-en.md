# Photo Metadata Extractor — Examples

Visual walkthrough of the application in action.

---

## 1. Run tab — ready to start

The **Run** tab shows the current configuration and lets you choose a directory, set the number of colors to extract, adjust the number of parallel workers, and launch processing.

![Run tab — ready state](screenshots/scrn1.png)

In this example:
- Scan directory is set to `/data/user/Desktop/camera`
- 5 dominant colors per photo
- 10 parallel workers out of 16 available CPU cores
- **Skip already processed** is checked — only new or changed photos will be processed

---

## 2. Processing in progress

After clicking **Run**, a progress bar appears along with live logs from the processing pipeline.

![Processing in progress](screenshots/scrn2.png)

The status indicator in the top-right corner switches to **Processing…**. The progress bar shows how many images have been processed (210 out of 1224 in this example). The log panel streams real-time output — you can see when batches are saved to the CSV file.

---

## 3. Photos tab — results table

Once processing is complete, switch to the **Photos** tab to browse results.

![Photos tab — results table](screenshots/scrn3.png)

The table shows all 1216 processed photos with:
- **Resolution** (e.g. 4912×3264)
- **Categories** detected by the AI (Portrait, Nature, Food, Indoor, Other…)
- **Colors** — small swatches of the dominant colors extracted from each photo
- **Processed** date

Use the search box to filter by filename or category name.

---

## 4. Photo detail page

Click any row to open the full detail view for that photo.

![Photo detail page](screenshots/scrn4.png)

The detail page shows:
- The photo itself on the left
- **File information** — name, resolution, format, full path, created/modified/processed dates
- **Content categories** with confidence bars (Architecture 38%, Other 35%, Nature 24% in this example)
- **Dominant colors** with HEX codes and percentage of image area (Lightblue 26.9%, Dimgray 22.0%)
