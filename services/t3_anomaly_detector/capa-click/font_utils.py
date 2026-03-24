"""
한글 폰트 설정 유틸리티

시스템의 사용 가능한 한글 폰트를 자동 감지하여 matplotlib에 설정합니다.
폰트 없으면 Google Fonts에서 Noto Sans CJK를 자동 다운로드합니다.
"""
import logging
import os
import platform
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from matplotlib import font_manager
from matplotlib import rcParams

logger = logging.getLogger(__name__)

# 시스템별 기본 한글 폰트 후보
FONT_CANDIDATES = {
    "Windows": [
        "맑은 고딕",  # Windows 기본 한글 폰트
        "궁서",
        "Arial Unicode MS",
        "Noto Sans CJK KR",
    ],
    "Darwin": [  # macOS
        "AppleGothic",
        "Apple SD Gothic Neo",
        "Noto Sans CJK KR",
    ],
    "Linux": [
        "Noto Sans CJK KR",
        "Noto Sans CJK JP",
        "DejaVu Sans",
    ],
}

# Google Fonts Noto Sans CJK 다운로드 URL
NOTO_SANS_URL = "https://github.com/noto-fonts/noto-cjk/raw/main/Sans/OTF/Korean/NotoSansCJKkr-Regular.otf"

# 폰트 캐시 디렉토리
FONT_CACHE_DIR = Path.home() / ".cache" / "anomaly_detector" / "fonts"


def find_available_font() -> str | None:
    """
    시스템에서 사용 가능한 한글 폰트를 찾아 반환

    Returns:
        사용 가능한 폰트 이름, 없으면 None
    """
    system = platform.system()
    candidates = FONT_CANDIDATES.get(system, FONT_CANDIDATES["Linux"])

    available_fonts = {f.name for f in font_manager.fontManager.ttflist}

    for font_name in candidates:
        if font_name in available_fonts:
            logger.debug(f"한글 폰트 찾음: {font_name}")
            return font_name

    logger.debug(f"시스템 한글 폰트 없음 (찾던 후보: {candidates})")
    return None


def download_noto_sans() -> Path | None:
    """
    Google Fonts에서 Noto Sans CJK KR 다운로드

    Returns:
        다운로드한 폰트 파일 경로, 실패 시 None
    """
    try:
        # 캐시 디렉토리 생성
        FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        font_path = FONT_CACHE_DIR / "NotoSansCJKkr-Regular.otf"

        # 이미 다운로드되었으면 스킵
        if font_path.exists():
            logger.debug(f"캐시된 폰트 사용: {font_path}")
            return font_path

        logger.info(f"Noto Sans CJK KR 다운로드 중... ({NOTO_SANS_URL})")

        # 다운로드
        urllib.request.urlretrieve(NOTO_SANS_URL, font_path)

        if font_path.exists():
            logger.info(f"폰트 다운로드 완료: {font_path}")
            return font_path
        else:
            logger.warning("폰트 다운로드 실패")
            return None

    except Exception as e:
        logger.warning(f"Noto Sans CJK 다운로드 실패: {e}")
        return None


def register_font(font_path: Path) -> bool:
    """
    폰트 파일을 matplotlib에 등록

    Args:
        font_path: 폰트 파일 경로

    Returns:
        등록 성공 여부
    """
    try:
        font_manager.fontManager.addfont(str(font_path))
        logger.info(f"폰트 등록: {font_path.name}")
        return True
    except Exception as e:
        logger.warning(f"폰트 등록 실패: {e}")
        return False


def setup_font():
    """
    matplotlib에 한글 폰트 설정

    1. 시스템 폰트 탐색
    2. 없으면 Google Fonts에서 자동 다운로드
    3. 폴백: 영문 폰트만 사용
    """
    # 1. 시스템 폰트 찾기
    font = find_available_font()
    if font:
        rcParams["font.sans-serif"] = [font, "DejaVu Sans", "Arial"]
        logger.info(f"한글 폰트 설정: {font}")
        rcParams["axes.unicode_minus"] = False
        return

    # 2. Google Fonts에서 다운로드
    logger.info("시스템 한글 폰트 없음. Google Fonts에서 자동 다운로드합니다...")
    font_path = download_noto_sans()

    if font_path and register_font(font_path):
        rcParams["font.sans-serif"] = ["Noto Sans CJK KR", "DejaVu Sans", "Arial"]
        logger.info("한글 폰트 설정: Noto Sans CJK KR (다운로드됨)")
        rcParams["axes.unicode_minus"] = False
        return

    # 3. 폴백: 영문 폰트만 사용
    rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    rcParams["axes.unicode_minus"] = False
    logger.warning("한글 폰트 설정 실패. 영문 폰트만 사용합니다.")
