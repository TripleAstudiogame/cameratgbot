"""Stable project root — avoids wrong DB/logs when cwd is not the app folder (Task Scheduler, services)."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
