from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TEST = ROOT / 'test'
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TEST))
