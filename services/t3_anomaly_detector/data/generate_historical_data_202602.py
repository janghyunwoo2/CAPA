import csv
from datetime import datetime, timedelta
import random

hourly_data = {
    "00": 53610, "01": 50485, "02": 55757, "03": 49231, "04": 49485,
    "05": 50835, "06": 49702, "07": 163757, "08": 175635, "09": 135569,
    "10": 135689, "11": 608749, "12": 580096, "13": 609054, "14": 232266,
    "15": 232997, "16": 239843, "17": 824193, "18": 817211, "19": 839582,
    "20": 795885, "21": 395409, "22": 424550, "23": 412630
}

output_file = 'data/historical_data_202602.csv'
rows = [['timestamp', 'impression_count']]

start_date = datetime(2026, 2, 1, 0, 0, 0)
end_date = datetime(2026, 3, 1, 0, 0, 0)

current = start_date
while current < end_date:
    hour_str = f"{current.hour:02d}"
    hourly_count = hourly_data[hour_str]
    count_per_5min = hourly_count / 12

    for i in range(12):
        ts = current + timedelta(minutes=i*5)
        random_factor = random.uniform(0.9, 1.1)
        count = int(count_per_5min * random_factor)
        rows.append([ts.strftime('%Y-%m-%d %H:%M:%S'), str(count)])

    current += timedelta(hours=1)

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print("[OK] 파일 생성 완료: " + output_file)
print("[INFO] 총 행: " + str(len(rows)))
