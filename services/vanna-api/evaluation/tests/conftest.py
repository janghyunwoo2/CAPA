import sys
from pathlib import Path

# evaluation/ 디렉토리를 sys.path에 추가하여 spider_evaluation 직접 import 가능하게 함
sys.path.insert(0, str(Path(__file__).parent.parent))
