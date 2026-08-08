from fastapi import *
from fastapi.responses import FileResponse
import os
import mysql.connector
from dotenv import load_dotenv
from fastapi.responses import FileResponse, JSONResponse


app=FastAPI()
load_dotenv()

# Static Pages (Never Modify Code in this Block)
@app.get("/", include_in_schema=False)
async def index(request: Request):
	return FileResponse("./static/index.html", media_type="text/html")

@app.get("/attraction/{id}", include_in_schema=False)
async def attraction(request: Request, id: int):
	return FileResponse("./static/attraction.html", media_type="text/html")

@app.get("/booking", include_in_schema=False)
async def booking(request: Request):
	return FileResponse("./static/booking.html", media_type="text/html")

@app.get("/thankyou", include_in_schema=False)
async def thankyou(request: Request):
	return FileResponse("./static/thankyou.html", media_type="text/html")

# ---------------------------------------------------
# Attraction APIs (Part 1-2)
# ---------------------------------------------------
@app.get("/api/categories")
def get_categories():
    conn = mysql.connector.connect(
		host=os.getenv("DB_HOST"),
		user=os.getenv("DB_USER"),
		password=os.getenv("DB_PASSWORD"),
		database=os.getenv("DB_NAME"),
  		charset="utf8mb4"
	)
    # print("Connect Successful")
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT category FROM attractions")
    rows = cursor.fetchall()
    # print(rows)
    cursor.close()
    conn.close()
    
    return {"data":[row["category"] for row in rows]}

@app.get("/api/mrts")
def get_mrts():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT mrt FROM attractions "
                   "WHERE mrt IS NOT NULL "
                   "GROUP BY mrt "
                   "ORDER BY COUNT(*) DESC"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {"data":[row["mrt"] for row in rows]}


@app.get("/api/attraction/{id}")
def get_attraction(id: int):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4"
    )
    cursor = conn.cursor(dictionary=True)

    # 1. 查景點本體
    cursor.execute("SELECT * FROM attractions WHERE id = %s", (id,))
    attraction = cursor.fetchone()

    # 2. 查不到就回 400
    if attraction is None:
        cursor.close()
        conn.close()
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "景點編號不正確"}
        )

    # 3. 查圖片，組成陣列
    cursor.execute(
        "SELECT url FROM attraction_images WHERE attraction_id = %s", (id,)
    )
    attraction["images"] = [row["url"] for row in cursor.fetchall()]

    # 4. Decimal 轉 float
    attraction["lat"] = float(attraction["lat"])
    attraction["lng"] = float(attraction["lng"])

    cursor.close()
    conn.close()

    return {"data": attraction}


@app.get("/api/attractions")
def get_attractions(page: int = 0, keyword: str = None, category: str = None):
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4"
    )
    cursor = conn.cursor(dictionary=True)

    # 1. 有哪些條件就收集哪些
    conditions, params = [], []

    if keyword:
        conditions.append("(mrt = %s OR name LIKE %s)")
        params.append(keyword)
        params.append(f"%{keyword}%")

    if category:
        conditions.append("category = %s")
        params.append(category)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # 2. 多取一筆，判斷還有沒有下一頁
    sql = f"SELECT * FROM attractions {where} ORDER BY id LIMIT %s OFFSET %s"
    cursor.execute(sql, params + [9, page * 8])
    rows = cursor.fetchall()

    if len(rows) > 8:
        next_page = page + 1
        rows = rows[:8]
    else:
        next_page = None

    # 3. 一次撈完這 8 個景點的所有圖片
    ids = [r["id"] for r in rows]
    img_map = {}

    if ids:
        placeholders = ", ".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT attraction_id, url FROM attraction_images "
            f"WHERE attraction_id IN ({placeholders})",
            ids
        )
        for row in cursor.fetchall():
            img_map.setdefault(row["attraction_id"], []).append(row["url"])

    # 4. 組裝
    for r in rows:
        r["images"] = img_map.get(r["id"], [])
        r["lat"] = float(r["lat"])
        r["lng"] = float(r["lng"])

    cursor.close()
    conn.close()

    return {"nextPage": next_page, "data": rows}
