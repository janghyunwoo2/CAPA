"""
PromptLoader — YAML 기반 프롬프트 로더 (FR-PE-04)
- prompts/*.yaml 파일 로드 + Jinja2 변수 렌더링
- 파일 mtime 감지 기반 캐시 (핫 리로드: 서버 재시작 없이 프롬프트 수정 반영)
- YAML 없거나 파싱 오류 시 빈 딕셔너리 반환 → 호출부 fallback 처리
"""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import Template, TemplateError

logger = logging.getLogger(__name__)

# prompts/ 디렉터리 기본 경로 (vanna-api 루트 기준)
_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PromptLoader:
    """YAML 기반 프롬프트 로더 — 핫 리로드 지원"""

    def __init__(self, prompts_dir: Optional[Path] = None) -> None:
        self._prompts_dir = prompts_dir or _DEFAULT_PROMPTS_DIR
        self._cache: dict[str, dict] = {}
        self._mtime: dict[str, float] = {}

    def load(self, name: str, **kwargs: Any) -> dict[str, str]:
        """YAML 프롬프트 로드 + Jinja2 렌더링.

        Args:
            name: YAML 파일명 (확장자 제외, 예: "sql_generator")
            **kwargs: Jinja2 템플릿 변수 (예: today="2026-03-23")

        Returns:
            렌더링된 프롬프트 딕셔너리.
            파일 없거나 오류 시 빈 딕셔너리 반환 → 호출부에서 fallback 처리.
        """
        path = self._prompts_dir / f"{name}.yaml"

        if not path.exists():
            logger.warning(f"프롬프트 파일 없음: {path}, fallback 사용")
            return {}

        mtime = path.stat().st_mtime
        if name not in self._cache or self._mtime.get(name) != mtime:
            try:
                raw = path.read_text(encoding="utf-8")
                self._cache[name] = yaml.safe_load(raw) or {}
                self._mtime[name] = mtime
                logger.info(f"프롬프트 로드/갱신: {name}.yaml")
            except (yaml.YAMLError, OSError) as e:
                logger.error(f"프롬프트 파일 파싱 실패: {name}.yaml — {e}")
                return {}

        rendered: dict[str, str] = {}
        for key, value in self._cache[name].items():
            if isinstance(value, str) and kwargs:
                try:
                    rendered[key] = Template(value).render(**kwargs)
                except TemplateError as e:
                    logger.warning(f"템플릿 렌더링 실패 ({name}.{key}): {e}, 원본 사용")
                    rendered[key] = value
            else:
                rendered[key] = value

        return rendered


# 모듈 레벨 싱글턴
_loader = PromptLoader()


def load_prompt(name: str, **kwargs: Any) -> dict[str, str]:
    """편의 함수 — 모듈 레벨 싱글턴으로 로드"""
    return _loader.load(name, **kwargs)
