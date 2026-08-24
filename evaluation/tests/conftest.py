"""Permite ejecutar la suite desde la raíz del repositorio o desde evaluation/."""

from __future__ import annotations

import sys
from pathlib import Path


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))
