"""Reusable core layer for acceptance-agent business workflows."""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
API_APP_ROOT = ROOT_DIR / "apps" / "api"
if str(API_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(API_APP_ROOT))
