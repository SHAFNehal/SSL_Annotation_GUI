"""Build lightweight manual or self-contained AI desktop distributions."""

import argparse
import os
from pathlib import Path
import sys
from src.branding import EXECUTABLE_NAME, LOGO_PATH

ROOT = Path(__file__).resolve().parent


def build_arguments(ai=False, platform=None):
    platform = platform or sys.platform
    name = EXECUTABLE_NAME + ("-AI" if ai else "")
    separator = ";" if platform == "win32" else ":"
    args = [str(ROOT / "main.py"), f"--name={name}", "--onedir" if ai else "--onefile",
            "--windowed", "--clean", "--noconfirm", f"--distpath={ROOT / 'dist'}",
            f"--workpath={ROOT / 'build' / name}", f"--specpath={ROOT / 'build'}",
            f"--add-data={ROOT / 'src' / 'icons'}{separator}src/icons"]
    if ai:
        # Include Transformers' dynamic model imports, source files, and metadata.
        args += ["--collect-all=transformers", "--collect-all=tokenizers",
                 "--collect-all=safetensors", "--collect-all=torchvision",
                 "--recursive-copy-metadata=transformers", "--copy-metadata=torch",
                 "--copy-metadata=torchvision", "--hidden-import=src.ai_worker"]
    else:
        args += [f"--exclude-module={module}" for module in
                 ("torch", "torchvision", "transformers", "tokenizers", "safetensors", "huggingface_hub")]
    if platform in ("win32", "darwin"):
        args.append(f"--icon={LOGO_PATH}")
    if platform == "darwin":
        args.append(f"--osx-bundle-identifier=edu.shsu.ssl.annotationstudio.{'ai' if ai else 'app'}")
    return args


def build_executable(ai=False):
    import PyInstaller.__main__

    os.chdir(ROOT)
    (ROOT / "build").mkdir(exist_ok=True)
    PyInstaller.__main__.run(build_arguments(ai))
    name = EXECUTABLE_NAME + ("-AI" if ai else "")
    print(f"Build complete: {ROOT / 'dist' / name}")
    if ai:
        print("Distribute the entire AI folder (or macOS .app), not just its executable.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ai", action="store_true", help="Bundle optional AI dependencies as an onedir distribution")
    build_executable(parser.parse_args().ai)
