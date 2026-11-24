# SSL Annotation Studio: Quick Start Guide

Developed by the **Stochastic Simulation Lab (SSL)**. Development and funding
credits are also available inside the tool under **Help > About**.

## Installation

### Option 1: Run from Source (Recommended for Development)

1. **Install Python 3.9 or higher** if not already installed
   - Download from https://www.python.org/downloads/
   - Make sure to check "Add Python to PATH" during installation

2. **Install uv**, then run the following commands from this tool's folder.
   uv creates and manages its virtual environment automatically.

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Run the application:**
   ```bash
   uv run python main.py
   ```
   Or use the run scripts:
   - Windows: `run.bat`
   - Linux/Mac: `./run.sh`

### Option 2: Build Standalone Executable

1. **Install dependencies** (including PyInstaller):
   ```bash
   uv sync --group build
   ```

2. **Build the executable:**
   ```bash
   uv run --group build python build.py
   ```

3. **Find your executable:**
   - Windows: `dist/SSLAnnotationStudio.exe`
   - macOS: `dist/SSLAnnotationStudio.app`
   - Linux: `dist/SSLAnnotationStudio`

The executable is completely standalone - no Python installation needed!

For an **AI-enabled** build:

```bash
uv run --extra ai --group build python build.py --ai
```

Use the full `dist/SSLAnnotationStudio-AI/` folder (Windows/Linux) or
`dist/SSLAnnotationStudio-AI.app` (macOS). Do not copy only its inner executable.
Model weights download on first AI use; they are not embedded in the bundle.

The GitHub workflow builds both editions for all three operating systems and
uploads separate artifacts. GitHub's AI downloads are CPU-based, so select
`auto` or `cpu`. Extract the contained zip/tar.gz completely before launching.
For GPU support, build locally with a compatible CUDA PyTorch environment.
See README.md for workflow location, tests, and artifact details.

## First Steps

1. **Open a folder with images:**
   - Click **Open Folder** in the header
   - Select a folder containing your images (JPG, PNG, etc.)

2. **Create your first annotation:**
   - Choose the **Active label** on the right (use **Add Label** if needed)
   - Click **Draw Box** or press `B`
   - Click and drag on the image to draw a bounding box
   - The new box uses your active label and is selected for editing
   - Use **Select** (`S`) to move/resize it or change its label

3. **Navigate between images:**
   - Use arrow keys (← →) or A/D keys
   - Single-click images in the left sidebar, or use **Go to** for an image number
   - Search filenames or filter **Without boxes** / **With boxes**; Previous/Next follows these filters

4. **Your annotations are automatically saved** when you navigate between images!

Changes also autosave after about one second of inactivity. Unchanged projects
are not rewritten. Original image files and same-stem sidecar XMLs are preserved.
The header shows **Saved**, **Unsaved changes**, or **Save failed**. The progress
bar counts images with boxes, not reviewed/approved images.

## Optional AI Assist

From **this tool's folder**, enable AI support and launch:

```bash
uv sync --extra ai
uv run --extra ai python main.py
```

Open an image folder, add the correct species label, and click **AI Assist...**.
Choose the current image or all unannotated/unprocessed images, enter a visual
prompt such as `a moth; an adult moth`, then generate drafts. Existing boxes
are never overwritten. `auto` uses a CUDA GPU when available, otherwise CPU.
The first run downloads model weights; images are processed locally.

Successful generation returns to the canvas automatically; **Stop** is only
needed to cancel a running job. If errors occur, inspect them and choose
**Review Drafts** or **Close**. Correct boxes in the canvas and click **Approve**
or **Reject**. Use the AI review filters on the left. Only approved AI images
are exported. Empty detections require correction or rejection; edits reopen
approval. Rejection keeps images and boxes rather than deleting them.

AI Assist is self-contained: the sibling `labeling_pipeline` folder is not
required. Existing run scripts also work after installing the AI dependencies.
Use `uv sync --extra ai` rather than plain `uv sync` to retain those packages.
See README.md for review safeguards and troubleshooting.

## Tips

- **Fix a label name**: Select it under Labels, click **Rename Label...**, and enter the corrected name. All boxes using that label are updated; AI approvals must be reviewed again. Export again to update training files.
- **Undo/Redo**: Press `Ctrl+Z` to undo, `Ctrl+Y` to redo
- **Multi-select**: Hold `Ctrl` and click multiple boxes, or drag a selection rectangle
- **Quick class assignment**: Press number keys 1-9, 0 to assign classes instantly
- **Zoom**: Use `Ctrl + Mouse Wheel` to zoom in/out
- **Fit to window**: Press `Ctrl+0` to fit image to window

## Export Formats

Click **Export Labels** or press **Ctrl+Shift+E** to export all three formats.
For a new project, `project.json` and `exports/` are inside the selected image folder:

- **VOC**: `exports/voc/Annotations/*.xml` - Pascal VOC format
- **COCO**: `exports/coco/annotations.json` - COCO format (single JSON file)
- **YOLO**: `exports/yolo/labels/*.txt` + `classes.txt` - YOLO format

Exports are generated only when requested, keeping browsing and autosave fast.
Export again after editing to refresh the training files. Saved project data
takes priority over stale exports so deleted annotations do not reappear.
Older matching parent-directory projects retain their original locations.

## Troubleshooting

**Problem**: "No module named 'PySide6'"
- **Solution**: Run `uv sync`, then start with `uv run python main.py`.

**Problem**: Images don't load
- **Solution**: Make sure your images are in common formats (JPG, PNG, BMP, TIFF, WEBP)

**Problem**: Can't build executable
- **Solution**: Run `uv run --group build python build.py`. PyInstaller is optional for normal annotation.

## Need Help?

Check the full README.md for more detailed information and keyboard shortcuts.

## Development And Funding

SSL Annotation Studio was developed by the **Stochastic Simulation Lab (SSL)**.
This project was developed with funding support from the United States Department
of Agriculture (USDA).

**Funding PI:** Syed Hasib Akhter Faruqui.

**Website:** [www.shafnehal.com](https://www.shafnehal.com/).
