"""Isolated JSON-lines worker: no Qt imports and no writes to source images."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from contextlib import ExitStack, redirect_stdout, redirect_stderr

from PIL import Image
from .ai_backend import GroundedDetector

PREFIX = "ANNOTATION_AI "
EVENT_STREAM = None


def emit(event, **values):
    print(PREFIX + json.dumps(dict(event=event, **values), allow_nan=False), file=EVENT_STREAM or sys.stdout, flush=True)


def process(request, detector_factory=GroundedDetector):
    from .ai_backend import sanitize_boxes

    config = request["config"]
    for name in ("box_threshold", "text_threshold", "nms_threshold"):
        if not 0 <= config[name] <= 1:
            raise ValueError(f"Invalid {name}")
    if not config["prompts"] or not all(isinstance(p, str) and p.strip() for p in config["prompts"]):
        raise ValueError("Enter a visual description, such as 'an adult moth'.")
    emit("status", message="Loading Grounding DINO; first use may download model weights.")
    detector = detector_factory(config, request["device"])
    for index, source in enumerate(request["images"]):
        path = Path(source)
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with Image.open(path) as original:
                orientation = original.getexif().get(274, 1)
                image = original.convert("RGB")
            boxes = sanitize_boxes(detector.predict(image), image.width, image.height,
                                   config["box_threshold"], config["nms_threshold"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Image changed during inference; draft discarded.")
            emit("result", filepath=str(path), width=image.width, height=image.height,
                 boxes=boxes, source_sha256=digest, model_revision=detector.revision,
                 exif_orientation=orientation, completed=index + 1)
        except Exception as exc:
            emit("image_error", filepath=str(path), message=str(exc), completed=index + 1)
    emit("complete")


def main():
    global EVENT_STREAM
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--events", type=Path, help="Event channel for windowed executables without stdout")
    parser.add_argument("--log-file", type=Path)
    args = parser.parse_args()
    with ExitStack() as stack:
        if args.events:
            EVENT_STREAM = stack.enter_context(args.events.open("a", encoding="utf-8"))
        if args.log_file:
            log = stack.enter_context(args.log_file.open("a", encoding="utf-8"))
            stack.enter_context(redirect_stdout(log))
            stack.enter_context(redirect_stderr(log))
        try:
            process(json.loads(args.request.read_text(encoding="utf-8")))
        except Exception as exc:
            emit("fatal", message=f"{type(exc).__name__}: {exc}")
            return 1
        finally:
            EVENT_STREAM = None
    return 0


if __name__ == "__main__":
    sys.exit(main())
