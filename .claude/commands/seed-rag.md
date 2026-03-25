# ChromaDB RAG 재시딩

로컬 e2e 환경의 vanna-api 컨테이너에서 실행합니다.
`./scripts`가 볼륨 마운트되어 있어 로컬 최신 파일이 바로 사용됩니다.

**Step 1. 컬렉션 초기화**
```bash
docker exec capa-vanna-api-e2e python -c "
import chromadb, os
client = chromadb.HttpClient(host='chromadb', port=8000)
for name in ['ddl', 'sql', 'documentation']:
    try:
        client.delete_collection(name)
        print(f'삭제: {name}')
    except Exception as e:
        print(f'건너뜀({name}): {e}')
print('초기화 완료')
"
```

**Step 2. 재시딩**
```bash
docker exec capa-vanna-api-e2e python scripts/seed_chromadb.py 2>&1 | grep -E "완료|ERROR|시작|={10,}"
```

**Step 3. 검증**
```bash
docker exec capa-vanna-api-e2e python -c "
import chromadb, os
client = chromadb.HttpClient(host='chromadb', port=8000)
for c in client.list_collections():
    print(f'{c.name}: {client.get_collection(c.name).count()}개')
docs = client.get_collection('documentation').get(limit=200, include=['documents'])['documents']
checks = {'OFFSET 미지원': 'OFFSET', 'ROW_NUMBER': 'ROW_NUMBER', 'DATEDIFF': 'DATEDIFF', 'CTR 정의': 'CTR', '파티션 규칙': '파티션'}
print()
for label, kw in checks.items():
    print(f'  {label}: {\"✅\" if any(kw in d for d in docs) else \"❌\"}')
"
```
