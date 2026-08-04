# Import tools
import os
import mysql.connector
import json #Python 內建，用來讀 JSON 檔
import re #內建正規表達式工具，拆圖片網址用
from dotenv import load_dotenv
load_dotenv()

# Load the JSON file
with open("data/taipei-attractions.json", encoding="utf-8-sig") as f:
    data=json.load(f)
# Test the result
#print(len(data["list"]))

# Get the two key values
img_host = data["img_host"]
attractions = data["list"]

# To see the first data
a = attractions[0]

# Print the nine columns of the first attraction
print("id :", a["_id"])
print("name :", a["name"])
print("category :", a["CAT"])
print("description:", a["description"][:30])
print("address  :", a["address"])
print("transport:", a["direction"][:30])
print("mrt      :", a["MRT"])
print("lat      :", a["latitude"])
print("lng      :", a["longitude"])

# Split the glued image paths of the first attraction
urls = re.findall(r'/imgs/[^/]+?\.jpg', a["imgurls"])
print("找到", len(urls), "張")
print(urls)

# Count images across all 58 attractions (expect 281)
total = 0
for a in attractions:
    total += len(re.findall(r'/imgs/[^/]+?\.jpg', a["imgurls"]))
print("總圖片數:", total)

# Prepend the host to build full image URLs
images = [img_host + u for u in urls]
print(images)

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

# Commit and close
conn.commit()
cursor.close()
conn.close()
print("匯入完成")


# 驗收用的指令（在終端機執行，不是 Python）
# mysql -u tdt -p taipei_day_trip -e "
# SELECT COUNT(*) AS attractions FROM attractions;
# SELECT COUNT(*) AS images FROM attraction_images;
# SELECT COUNT(DISTINCT category) AS cats FROM attractions;
# SELECT COUNT(DISTINCT mrt) AS mrts FROM attractions WHERE mrt IS NOT NULL;
# SELECT * FROM attractions WHERE id = 1\G"
