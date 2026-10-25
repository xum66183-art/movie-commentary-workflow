"""Make the adjacent shared package available to source-tree script entry points."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
