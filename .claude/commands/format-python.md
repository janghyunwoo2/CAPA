# Python 코드 포맷팅

CAPA 프로젝트의 Python 파일을 Black과 isort로 포맷합니다.

```bash
python -m black services/ --line-length 100
python -m isort services/ --profile black
```
