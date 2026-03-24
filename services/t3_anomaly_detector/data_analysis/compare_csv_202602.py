import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

def generate_comparison():
    # 경로 설정 (절대 경로)
    base_dir = r"c:\Users\Dell3571\Desktop\projects\CAPA\services\t3_anomaly_detector"
    imp_csv = os.path.join(base_dir, "capa-impression", "data", "historical_data_202602_from_athena.csv")
    clk_csv = os.path.join(base_dir, "capa-click", "data", "historical_click_data_202602_from_athena.csv")
    conv_csv = os.path.join(base_dir, "capa-conversion", "data", "historical_conversion_data_202602_from_athena.csv")
    
    # 결과 저장 경로 (현재 스크립트 위치와 동일)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, "comparison_result_202602.png")

    print(f"[{datetime.now()}] CSV 데이터 로드 중...")
    
    # 데이터 로드 (3일치 = 288 * 3 = 864개)
    if not all([os.path.exists(imp_csv), os.path.exists(clk_csv), os.path.exists(conv_csv)]):
        print("❌ CSV 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        return

    df_imp = pd.read_csv(imp_csv, parse_dates=["timestamp"]).head(864)
    df_clk = pd.read_csv(clk_csv, parse_dates=["timestamp"]).head(864)
    df_conv = pd.read_csv(conv_csv, parse_dates=["timestamp"]).head(864)

    # [수정] 전환 지표가 0인 경우 그래프에서 아예 안 보이도록 NaN 처리
    import numpy as np
    df_conv['conversion_count'] = df_conv['conversion_count'].replace(0, np.nan)

    # 시각화 시작
    fig, ax1 = plt.subplots(figsize=(16, 8))

    # 노출(Impression) - 왼쪽 축
    color_imp = 'tab:blue'
    ax1.set_xlabel('Timestamp (2026-02-01 ~ 2026-02-03)')
    ax1.set_ylabel('Impression Count (Left)', color=color_imp, fontsize=12, fontweight='bold')
    ax1.plot(df_imp['timestamp'], df_imp['impression_count'], color=color_imp, label='Impression', linewidth=1.5, alpha=0.8)
    ax1.tick_params(axis='y', labelcolor=color_imp)
    ax1.grid(True, alpha=0.3)

    # 클릭(Click) & 전환(Conversion) - 오른쪽 축 공유
    ax2 = ax1.twinx()
    color_clk = 'tab:orange'
    color_conv = 'tab:red'
    ax2.set_ylabel('Click / Conversion Count (Right)', color='black', fontsize=12, fontweight='bold')
    ax2.plot(df_clk['timestamp'], df_clk['click_count'], color=color_clk, label='Click', linestyle='--', linewidth=1.5, alpha=0.6)
    
    # [수정] 전환 지표를 크고 굵은 별표(*) 마커로 강조 (0 제외 상태)
    ax2.plot(df_conv['timestamp'], df_conv['conversion_count'], color=color_conv, label='Conversion (Highlight)', 
             marker='*', markersize=12, markeredgecolor='black', linestyle='none')
    ax2.tick_params(axis='y', labelcolor='black')

    # 범례 합치기
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc='upper right')

    plt.title('2026-02 Traffic Comparison (3 Days): Imp vs Click vs Conv', fontsize=16, pad=20)
    fig.tight_layout()
    
    # 저장
    plt.savefig(output_path, dpi=150)
    print(f"✅ 비교 차트가 저장되었습니다: {output_path}")

if __name__ == "__main__":
    generate_comparison()
