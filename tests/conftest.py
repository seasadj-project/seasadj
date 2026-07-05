import sys
from pathlib import Path

# make src/seasadj importable without installation
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# repository root (holds 01_プログラム/ and 04_検証データ/)
REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "04_検証データ"
PARA_DIR = REPO_ROOT / "01_プログラム" / "para"
