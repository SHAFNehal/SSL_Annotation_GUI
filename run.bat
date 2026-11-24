@echo off
REM Run script for SSL Annotation Studio (Windows)

cd /d "%~dp0"
uv run python main.py
