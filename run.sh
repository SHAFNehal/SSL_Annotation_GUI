#!/bin/bash
# Run script for SSL Annotation Studio

cd -- "$(dirname -- "$0")" || exit 1
exec uv run python main.py
