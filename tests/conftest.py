import sys
from pathlib import Path

# The bot adds tools/ to sys.path at runtime (see agent.py); tests do the same.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
