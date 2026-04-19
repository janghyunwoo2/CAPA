"""
ChromaDB 시딩 상태 검증 스크립트 v2
pipeline-rag-optimization 적용 후 검증 기준:
  - ddl 컬렉션 미사용 (0건 또는 미존재)
  - sql 컬렉션: cosine 메트릭 + tables metadata 포함
  - documentation 컬렉션: cosine 메트릭 + 문장형 포맷 + DOCS_NEGATIVE_EXAMPLES
"""
import os
import chromadb

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

# ── 1. 컬렉션 목록 및 메트릭 ─────────────────────────────────────
print("=" * 60)
print("컬렉션 목록")
print("=" * 60)
for c in client.list_collections():
    col = client.get_collection(c.name)
    metric = (col.metadata or {}).get("hnsw:space", "L2(기본값)")
    cosine_ok = "✅" if metric == "cosine" else "❌"
    print(f"  {c.name:25s} count={col.count():4d}  metric={metric} {cosine_ok}")

# ── 2. DDL 컬렉션: Phase 2 이후 미사용 ──────────────────────────
print("\n" + "=" * 60)
print("DDL 컬렉션 검증 (Phase 2: 미사용이어야 함)")
print("=" * 60)
try:
    ddl_col = client.get_collection("ddl")
    count = ddl_col.count()
    status = "✅ 0건 (정상)" if count == 0 else f"⚠️  {count}건 잔존 (재시딩 필요)"
    print(f"  ddl 컬렉션 count: {count}  {status}")
except Exception:
    print("  ddl 컬렉션 미존재 ✅ (삭제됨)")

# ── 3. SQL 컬렉션: cosine + tables metadata ───────────────────────
print("\n" + "=" * 60)
print("SQL 컬렉션 검증")
print("=" * 60)
sql_col = client.get_collection("sql")
sql_data = sql_col.get(limit=200, include=["documents", "metadatas"])
sqls    = [m["sql"]    for m in sql_data["metadatas"] if m.get("sql")]
tables_list = [m.get("tables", "") for m in sql_data["metadatas"]]

print(f"  SQL 예제 수: {len(sqls)}")

# tables metadata 포함률
has_tables = sum(1 for t in tables_list if t)
pct = has_tables / len(tables_list) * 100 if tables_list else 0
icon = "✅" if pct >= 90 else "❌"
print(f"  tables metadata 포함: {has_tables}/{len(tables_list)} ({pct:.0f}%) {icon}")

# 테이블 분포
from collections import Counter
import ast
table_counter: Counter = Counter()
for t in tables_list:
    if not t:
        continue
    try:
        parsed = ast.literal_eval(t)
        if isinstance(parsed, list):
            for name in parsed:
                table_counter[name] += 1
    except Exception:
        pass
print(f"  테이블 분포: {dict(table_counter)}")

# 잘못된 패턴 체크
bad = [s for s in sqls if "SUM(impressions)" in s or "SUM(clicks)" in s]
print(f"  잘못된 컬럼(SUM(impressions/clicks)): {len(bad)}건 {'✅' if not bad else '❌'}")

# cosine 검증용 쿼리 테스트
try:
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    ef = SentenceTransformerEmbeddingFunction(model_name="jhgan/ko-sroberta-multitask")
    sql_col_ef = client.get_collection("sql", embedding_function=ef)
    result = sql_col_ef.query(query_texts=["어제 CTR은?"], n_results=3, include=["distances"])
    dists = result["distances"][0]
    print(f"  cosine 쿼리 테스트 ('어제 CTR은?') top-3 distances: {[round(d,4) for d in dists]}")
    all_lte_1 = all(d <= 1.001 for d in dists)
    print(f"  모든 distance ≤ 1.0 (cosine 범위): {'✅' if all_lte_1 else '❌'}")
except Exception as e:
    print(f"  cosine 쿼리 테스트 실패 (임베딩 모델 로드 필요): {e}")

# ── 4. Documentation 컬렉션 ──────────────────────────────────────
print("\n" + "=" * 60)
print("Documentation 컬렉션 검증")
print("=" * 60)
doc_col = client.get_collection("documentation")
docs = doc_col.get(limit=100, include=["documents"])["documents"]
print(f"  문서 수: {len(docs)}")

checks = {
    "CTR 퍼센트 형식 (ctr_percent)":       any("ctr_percent" in d for d in docs),
    "CVR 퍼센트 형식 (cvr_percent)":       any("cvr_percent" in d for d in docs),
    "문장형 포맷 (~합니다)":               any("합니다" in d for d in docs),
    "NULLIF 규칙 존재":                   any("NULLIF" in d for d in docs),
    "파티션 규칙 존재":                   any("파티션" in d for d in docs),
    "DOCS_NEGATIVE_EXAMPLES 오답패턴 존재": any("오답 패턴" in d for d in docs),
    "DOCS_SCHEMA_MAPPER 미포함":          not any("SUMMARY_EXCLUSIVE" in d for d in docs),
    "0~1 비율 규칙 미포함 (퍼센트로 교체)": not any("0~1 비율로 반환" in d for d in docs),
}
for label, ok in checks.items():
    print(f"  {'✅' if ok else '❌'} {label}")

# ── 5. 최종 판정 ─────────────────────────────────────────────────
print("\n" + "=" * 60)
all_pass = all(checks.values()) and pct >= 90
print(f"  최종 판정: {'✅ PASS' if all_pass else '❌ FAIL (위 항목 확인 필요)'}")
print("=" * 60)
