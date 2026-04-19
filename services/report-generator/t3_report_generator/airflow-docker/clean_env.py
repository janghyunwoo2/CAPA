import os

# 두 곳의 .env 파일을 모두 정화
paths = [
    r'c:\Users\Dell3571\Desktop\projects\CAPA\services\report-generator\t3_report_generator\airflow-docker\.env',
    r'c:\Users\Dell3571\Desktop\projects\CAPA\services\report-generator\t3_report_generator\.env'
]

for env_path in paths:
    print(f"Checking {env_path}...")
    if not os.path.exists(env_path):
        print("  File not found. Skip.")
        continue

    with open(env_path, 'rb') as f:
        content = f.read()

    if b'\x00' in content:
        print(f"  Found {content.count(b'\x00')} null bytes!")
        cleaned_content = content.replace(b'\x00', b'')
        with open(env_path, 'wb') as f:
            f.write(cleaned_content)
        print("  Cleaned null bytes successfully.")
    else:
        print("  No null bytes found in binary read.")

    # 정규화된 UTF-8로 다시 저장 (BOM 없이)
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            text = f.read()
        with open(env_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print("  Re-saved as clean UTF-8.")
    except UnicodeDecodeError as e:
        # 인코딩이 다를 수 있으므로 다른 인코딩 시도 (예: utf-16)
        print(f"  Encoding Error with UTF-8: {e}")
        try:
            with open(env_path, 'r', encoding='utf-16') as f:
                text = f.read()
            with open(env_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            print("  Recovered from UTF-16 and re-saved as clean UTF-8.")
        except Exception as e2:
            print(f"  Final Recovery Failed: {e2}")
