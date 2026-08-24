import sys
from pathlib import Path


PERFORMANCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PERFORMANCE_ROOT))
