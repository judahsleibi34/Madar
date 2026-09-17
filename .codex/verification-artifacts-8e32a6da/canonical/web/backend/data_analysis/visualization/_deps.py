import colorsys
import json
import math
import os
import re
import tempfile
import warnings
from pathlib import Path
from typing import Literal

import pandas as pd
import seaborn as sns
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_hex, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

def _configure_pygwalker_privacy() -> None:
    if os.getenv("PYGWALKER_TELEMETRY_ENABLED", "false").strip().lower() == "true":
        return
    config_root = Path(
        os.environ.setdefault(
            "XDG_CONFIG_HOME",
            str(Path(tempfile.gettempdir()) / "madar-config"),
        )
    )
    config_path = config_root / "pygwalker" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {}
    if config_path.is_file():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            config = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            config = {}
    config["privacy"] = "offline"
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")


try:
    _configure_pygwalker_privacy()
    import pygwalker as pyg
    from pygwalker.services.global_var import GlobalVarManager

    if os.getenv("PYGWALKER_TELEMETRY_ENABLED", "false").strip().lower() != "true":
        GlobalVarManager.set_privacy("offline")
except Exception:
    pyg = None


__all__ = [
    "colorsys",
    "math",
    "os",
    "re",
    "warnings",
    "Path",
    "Literal",
    "pd",
    "sns",
    "matplotlib",
    "plt",
    "LinearSegmentedColormap",
    "to_hex",
    "to_rgb",
    "Line2D",
    "Patch",
    "FuncFormatter",
    "arabic_reshaper",
    "get_display",
    "pyg",
]
