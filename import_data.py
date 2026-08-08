# Import tools
import os
import sys
import mysql.connector
import json #Python 內建，用來讀 JSON 檔
import re #內建正規表達式工具，拆圖片網址用
from dotenv import load_dotenv
load_dotenv()

# Load the JSON file
with open("data/taipei-attractions.json", encoding="utf-8-sig") as f:
    data=json.load(f)

# Get the two key values
img_host = data["img_host"]
attractions = data["list"]

# Guard: this script wipes the attractions table before re-importing.
# Ask for confirmation unless run with --force (e.g. python3 import_data.py --force)
if "--force" not in sys.argv:
    answer = input(f"即將清空並重新匯入 {os.getenv('DB_NAME')} 的景點資料，繼續？(yes/no) ")
    if answer.strip().lower() != "yes":
        print("已取消，資料庫未變動")
        sys.exit(0)

# Connect to DB
conn = mysql.connector.connect(
    host = os.getenv("DB_HOST"),
    user = os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    charset="utf8mb4"
)
cursor = conn.cursor()
print("Connect Succeed")

# Clear old rows so the script can re-run
# attraction_images has ON DELETE CASCADE, so its rows are removed too
cursor.execute("DELETE FROM attractions")

# Insert attractions, then their images
image_count = 0
for item in attractions:
    # 1. 先插景點
    cursor.execute(
        "INSERT INTO attractions (id, name, category, description, address, transport, mrt, lat, lng) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            item["_id"],
            item["name"],
            item["CAT"],
            item["description"],
            item["address"],
            item["direction"],
            item["MRT"],
            float(item["latitude"]),
            float(item["longitude"]),
        )
    )

    # 2. 再插圖片
    urls = re.findall(r'/imgs/[^/]+?\.jpg', item["imgurls"])
    rows = [(item["_id"], img_host + u) for u in urls]
    cursor.executemany(
        "INSERT INTO attraction_images (attraction_id, url) VALUES (%s, %s)",
        rows
    )
    image_count += len(rows)

# Commit and close
conn.commit()
cursor.close()
conn.close()
print(f"匯入完成：{len(attractions)} 筆景點、{image_count} 張圖片")


# 驗收用的指令（在終端機執行，不是 Python）
# mysql -u tdt -p taipei_day_trip -e "
# SELECT COUNT(*) AS attractions FROM attractions;
# SELECT COUNT(*) AS images FROM attraction_images;
# SELECT COUNT(DISTINCT category) AS cats FROM attractions;
# SELECT COUNT(DISTINCT mrt) AS mrts FROM attractions WHERE mrt IS NOT NULL;
# SELECT * FROM attractions WHERE id = 1\G"
