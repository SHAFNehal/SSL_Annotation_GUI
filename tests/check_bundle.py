"""CI: check the frozen GUI and AI worker, then archive the complete bundle."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.branding import EXECUTABLE_NAME


def paths(ai):
    name = EXECUTABLE_NAME + ("-AI" if ai else "")
    dist = ROOT / "dist"
    if platform.system() == "Darwin":
        bundle = dist / (name + ".app")
        return bundle, bundle / "Contents" / "MacOS" / name
    if ai:
        bundle = dist / name
        return bundle, bundle / (name + (".exe" if os.name == "nt" else ""))
    executable = dist / (name + (".exe" if os.name == "nt" else ""))
    return executable, executable


def check(executable, ai):
    with tempfile.TemporaryDirectory(prefix="annotation-bundle-check-") as directory:
        temp = Path(directory)
        report = temp / "startup.json"
        args = [str(executable), "--bundle-check", "--report", str(report)]
        if ai:
            args.append("--expect-ai")
        subprocess.run(args, check=True, timeout=120, cwd=temp)
        assert json.loads(report.read_text(encoding="utf-8"))["ok"], "Packaged GUI startup check failed"
        if not ai:
            return
        # Blank image is intentional: validate inference, not detector accuracy.
        source = temp / "sample.jpg"
        Image.new("RGB", (128, 128), "white").save(source)
        request = temp / "request.json"
        request.write_text(json.dumps(dict(device="cpu", images=[str(source)],
            config=dict(prompts=["an insect"], box_threshold=0.35, text_threshold=0.25, nms_threshold=0.5))))
        events, log = temp / "events.jsonl", temp / "worker.log"
        worker_env = os.environ.copy()
        worker_env.setdefault("OMP_NUM_THREADS", "2")
        worker_env.setdefault("MKL_NUM_THREADS", "2")
        result = subprocess.run([str(executable), "--ai-worker", "--request", str(request),
            "--events", str(events), "--log-file", str(log)], cwd=temp, timeout=600, env=worker_env)
        rows = [json.loads(line.removeprefix("ANNOTATION_AI ")) for line in events.read_text(encoding="utf-8").splitlines()] if events.exists() else []
        if result.returncode != 0 or [row["event"] for row in rows] != ["status", "result", "complete"]:
            details = log.read_text(encoding="utf-8", errors="replace") if log.exists() else "No worker log"
            raise RuntimeError(f"Packaged AI inference failed: {rows}\n{details}")


def archive(bundle, ai):
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    name = EXECUTABLE_NAME + ("-AI" if ai else "") + f"-{platform.system()}-{platform.machine()}"
    if os.name == "nt":
        # AI dependencies stay beside the executable in the zip.
        shutil.make_archive(str(release / name), "zip", root_dir=bundle.parent, base_dir=bundle.name)
    else:
        # Preserve executable permissions and macOS framework symlinks.
        with tarfile.open(release / (name + ".tar.gz"), "w:gz") as output:
            output.add(bundle, arcname=bundle.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=["manual", "ai"], required=True)
    ai = parser.parse_args().edition == "ai"
    bundle, executable = paths(ai)
    check(executable, ai)
    archive(bundle, ai)
