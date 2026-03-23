import chromadb
client = chromadb.HttpClient(host="chromadb", port=8000)

for c in client.list_collections():
    col = client.get_collection(c.name)
    print(c.name + ": " + str(col.count()))

ddl_col = client.get_collection("ddl")
ddl_docs = ddl_col.get(limit=10, include=["documents"])["documents"]
print("\n=== DDL 검증 ===")
print("ad_combined_log 존재:", any("ad_combined_log" in d and "summary" not in d for d in ddl_docs))
print("ad_combined_log_summary 존재:", any("ad_combined_log_summary" in d for d in ddl_docs))
print("is_click 컬럼:", any("is_click" in d for d in ddl_docs))
print("is_conversion 컬럼:", any("is_conversion" in d for d in ddl_docs))
print("cost_per_impression 컬럼:", any("cost_per_impression" in d for d in ddl_docs))

sql_col = client.get_collection("sql")
sql_data = sql_col.get(limit=100, include=["documents","metadatas"])
sqls = [m["sql"] for m in sql_data["metadatas"] if m.get("sql")]
print("\n=== SQL 검증 ===")
print("SQL 예제 수:", len(sqls))
bad = [s for s in sqls if "SUM(impressions)" in s or "SUM(clicks)" in s]
print("잘못된 컬럼(SUM(impressions/clicks)) 포함 수:", len(bad))
good = [s for s in sqls if "is_click" in s or "is_conversion" in s or "COUNT(*)" in s]
print("올바른 패턴(is_click/is_conversion/COUNT(*)) 수:", len(good))

doc_col = client.get_collection("documentation")
docs = doc_col.get(limit=100, include=["documents"])["documents"]
print("\n=== Documentation 검증 ===")
print("문서 수:", len(docs))
print("CTR 정의 존재:", any("CTR" in d for d in docs))
print("파티션 규칙 존재:", any("파티션" in d for d in docs))
print("device_type 존재:", any("device_type" in d for d in docs))
print("is_click 계산식 존재:", any("is_click" in d for d in docs))
print("NULLIF 규칙 존재:", any("NULLIF" in d for d in docs))
