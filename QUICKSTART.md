# SSL Annotation Studio: Quick Start

Developed by the **Stochastic Simulation Lab (SSL)**. See **Help > About** for credits.

## Run

Install Python 3.9+ and [uv](https://docs.astral.sh/uv/), then from this folder:

```bash
uv sync
uv run python main.py        # or run.bat (Windows) / ./run.sh (Linux, macOS)
```

## Annotate

1. Click **Open Folder** and select your images.
2. Choose or **Add Label** (right panel).
3. Press `B`, then drag on the image to draw a box.
4. Press `S` to move or resize. Use `A`/`D` to change images.
5. Press `Ctrl+Shift+E` to export.

Changes autosave after about one second idle and when you navigate. The header shows **Saved**, **Unsaved changes**, or **Save failed**.

## Export

**Export Labels** writes to `exports/` inside your image folder:

- VOC: `exports/voc/Annotations/*.xml`
- COCO: `exports/coco/annotations.json`
- YOLO: `exports/yolo/labels/*.txt` and `classes.txt`

Export again after editing to refresh the files.

## AI Assist (optional)

```bash
uv sync --extra ai
uv run --extra ai python main.py
```

1. Open a folder and add the species label.
2. Click **AI Assist...**, choose the scope, and enter a prompt like `a moth; an adult moth`.
3. Click **Generate Drafts**. Existing boxes are never overwritten.
4. Fix the boxes on the canvas, then **Approve** or **Reject**.

Only approved AI images are exported. The model downloads on first use, then runs locally.

## Build an Executable

```bash
uv run --group build python build.py                    # manual
uv run --extra ai --group build python build.py --ai    # AI (ship the whole folder)
```

Output goes to `dist/`. CI builds for all platforms are described in [README.md](README.md).

## Tips

- `Ctrl+Z` / `Ctrl+Y`: undo / redo
- `Ctrl`+click or drag: multi-select
- `1`-`9`, `0`: assign label by number
- `Ctrl+Wheel` zoom, `Ctrl+0` fit to window
- **Rename Label...** fixes a label name across all images

## Troubleshooting

- **No module named 'PySide6'**: run `uv sync`, then `uv run python main.py`.
- **Images don't load**: use JPG, PNG, BMP, TIFF, or WEBP.
- **Linux: Qt fails to start**: install `libegl1 libgl1 libxkbcommon0`.

Full details and shortcuts are in [README.md](README.md).

## Funding

Developed with funding support from the United States Department of Agriculture (USDA).
**Funding PI:** Syed Hasib Akhter Faruqui. **Website:** [www.shafnehal.com](https://www.shafnehal.com/)
