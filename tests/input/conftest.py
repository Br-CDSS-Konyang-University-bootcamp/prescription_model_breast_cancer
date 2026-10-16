import sys
from pathlib import Path

# team_project 폴더를 import 경로에 넣는다 (from src.input... 를 쓰기 위해)
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
