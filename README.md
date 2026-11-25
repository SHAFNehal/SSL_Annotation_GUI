# SSL Annotation Studio

<img src="src/icons/SSL_Lab_Logo_Final.png" alt="Stochastic Simulation Lab logo" width="320">

A desktop bounding-box annotation tool for computer vision datasets. Exports Pascal VOC, YOLO, and COCO. Optional AI Assist drafts boxes from text prompts.

Developed by the **Stochastic Simulation Lab (SSL)**. Runs on Windows, macOS, and Linux. Manual annotation works fully offline.

## Features

- Three-panel layout: image list, canvas, labels
- Filename search, with/without-box filters, jump to image number
- Undo/redo, multi-select, keyboard shortcuts
- Autosave after one second idle and before navigation
- On-demand export to VOC, YOLO, and COCO
- Imports same-stem Pascal VOC XMLs found beside images
- Optional AI Assist (Grounding DINO Tiny) with approve/reject review

## Install and Run

Requires Python 3.9+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python main.py
```

For AI Assist (Python 3.11 recommended):

```bash
uv sync --python 3.11 --extra ai
uv run --python 3.11 --extra ai python main.py
```

Plain `uv sync` removes the AI packages. Manual annotation still works.

With pip: `pip install -r requirements.txt`.

## Usage

1. **Open Folder** and pick your images. Existing VOC sidecar XMLs are imported.
2. Pick or **Add Label**, then press `B` and drag to draw a box.
3. Press `S` to move or resize. Change a selected box's label from the dropdown or with keys `0`-`9`.
4. Move between images with `A`/`D` or the arrow keys. Navigation follows the current filter.
5. **Export Labels** (`Ctrl+Shift+E`) writes the training files.

Notes:
- The progress bar counts images with at least one box. It does not track review.
- **Rename Label...** updates every image and keeps colors and coordinates. AI approvals using that label must be redone. Export again afterward.
- Exports run only on request. `project.json` is the working state.

### Shortcuts

| Action | Keys |
|---|---|
| Previous / next image | `←` `→` or `A` `D` |
| First / last image | `Home` / `End` |
| Select / Box / Pan | `S` / `B` / `H` |
| Delete box / select all / deselect | `Delete` / `Ctrl+A` / `Esc` |
| Assign label | `1`-`9`, `0` |
| Zoom / fit / 100% | `Ctrl+Wheel` / `Ctrl+0` / `Ctrl+1` |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` |
| Save / export | `Ctrl+S` / `Ctrl+Shift+E` |

## AI Assist

1. Open a folder and select the species label.
2. Click **AI Assist...** (or **AI > Generate Drafts**).
3. Choose **Current image** or **All unannotated, unprocessed images**. Existing boxes are never replaced.
4. Enter a visual description such as `a moth; an adult moth`. Semicolons separate prompts. Species names alone often work poorly.
5. Pick a device (`auto`, `cpu`, `cuda:0`, `cuda:1`) and click **Generate Drafts**. Defaults: box threshold 0.35, text threshold 0.25, NMS 0.5.
6. Review every box on the canvas, fix it, then **Approve** or **Reject**. The **Needs AI review**, **AI approved**, and **AI rejected** filters help.
7. **Export Labels**. Only approved AI images are exported.

The model downloads on first use (internet and a writable Hugging Face cache needed), then runs locally. Images are never uploaded. CPU inference can be slow.

**Review rules**
- Every generated image starts pending, including ones with no detections. No detections is not a verified negative.
- AI does not confirm species or life stage. The chosen label is applied to all boxes.
- Reject keeps the image and its boxes. **AI > Reset Current Review** returns it to pending.
- Editing boxes or labels, or changing the source image, invalidates approval.
- Pending and rejected images are omitted from VOC/YOLO and excluded from COCO. Original sidecar XMLs are never modified.
- `project.json` stores decisions, prompts, scores, model revision, and checksums.

## Build Executables

```bash
uv run --group build python build.py              # manual edition, single file
uv run --extra ai --group build python build.py --ai   # AI edition, folder
```

| Edition | Output |
|---|---|
| Manual | `dist/SSLAnnotationStudio` (`.exe` on Windows, `.app` on macOS) |
| AI | `dist/SSLAnnotationStudio-AI/` (`.app` on macOS) |

Distribute the whole AI folder or app, not just the inner executable. Model weights are not bundled. Builds are unsigned, so OS security warnings may appear.

### GitHub Actions

`.github/workflows/build.yml` builds both editions on Windows, Linux, and macOS. It runs on `v*` tags or manually. Each job runs the tests, checks the packaged app, and for AI runs CPU inference through the packaged worker. Artifacts are named `SSLAnnotationStudio-<edition>-<OS>-<arch>` and kept for 30 days. Windows downloads contain a zip, Linux and macOS a tar.gz. Extract fully before launching.

CI AI builds use CPU PyTorch, so choose `auto` or `cpu`. For GPU, build locally with a CUDA PyTorch.

To run the same check locally:

```bash
uv run --extra ai --group build python tests/check_bundle.py --edition ai
```

## Project Files

Created in the selected image folder:

```
project.json        working state
project.json.bak    previous save
exports/
  voc/Annotations/*.xml
  coco/annotations.json
  yolo/labels/*.txt + classes.txt
```

Saves are atomic and keep a backup. A failed save blocks navigation, and closing then requires an explicit discard. An older parent-folder `project.json` is still used if its `image_folder` matches.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

Tests run offscreen in temporary folders. An optional real-model smoke test runs when `AI_SMOKE_IMAGE` is set:

```bash
AI_SMOKE_IMAGE=/path/to/moth.jpg uv run --extra ai python -m unittest discover -s tests -p test_ai_integration.py -v
```

On Linux, Qt needs system libraries such as `libegl1`, `libgl1`, and `libxkbcommon0`.

## License

MIT

## Funding

Developed with funding support from the United States Department of Agriculture (USDA).
**Funding PI:** Syed Hasib Akhter Faruqui. **Website:** [www.shafnehal.com](https://www.shafnehal.com/)
