from fastapi import *
from fastapi.responses import FileResponse, JSONResponse
import contextlib
import os
import mysql.connector
from dotenv import load_dotenv


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
# Shared helpers
# ---------------------------------------------------
PAGE_SIZE = 8


@contextlib.contextmanager
def dict_cursor():
    """Open a MySQL connection, yield a dict cursor, always close both."""
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
    )
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
    finally:
        cursor.close()
        conn.close()


def fetch_images_for_ids(cursor, ids):
    """Fetch every image of the given attractions in one query, grouped by id."""
    if not ids:
        return {}
    placeholders = ", ".join(["%s"] * len(ids))
    cursor.execute(
        "SELECT attraction_id, url FROM attraction_images "
        f"WHERE attraction_id IN ({placeholders})",
        ids,
    )
    img_map = {}
    for row in cursor.fetchall():
        img_map.setdefault(row["attraction_id"], []).append(row["url"])
    return img_map


def normalize_attraction(row, images):
    """Shape a DB row into the response format: images array, lat/lng as numbers."""
    row["images"] = images
    row["lat"] = float(row["lat"])      # DECIMAL is not JSON serializable
    row["lng"] = float(row["lng"])
    return row


# ---------------------------------------------------
# Attraction APIs (Part 1-2)
# ---------------------------------------------------
@app.get("/api/categories")
def get_categories():
    with dict_cursor() as cursor:
        cursor.execute("SELECT DISTINCT category FROM attractions")
        rows = cursor.fetchall()

    return {"data": [row["category"] for row in rows]}


@app.get("/api/mrts")
def get_mrts():
    with dict_cursor() as cursor:
        cursor.execute(
            "SELECT mrt FROM attractions "
            "WHERE mrt IS NOT NULL "
            "GROUP BY mrt "
            "ORDER BY COUNT(*) DESC"
        )
        rows = cursor.fetchall()

    return {"data": [row["mrt"] for row in rows]}


@app.get("/api/attraction/{id}")
def get_attraction(id: int):
    with dict_cursor() as cursor:
        # 1. 查景點本體
        cursor.execute("SELECT * FROM attractions WHERE id = %s", (id,))
        attraction = cursor.fetchone()

        # 2. 查不到就回 400（依 API 規格書，此端點的錯誤碼是 400 而非 404）
        if attraction is None:
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "景點編號不正確"},
            )

        # 3. 查圖片
        images = fetch_images_for_ids(cursor, [id]).get(id, [])

    return {"data": normalize_attraction(attraction, images)}


@app.get("/api/attractions")
def get_attractions(page: int = 0, keyword: str = None, category: str = None):
    # 1. 有哪些條件就收集哪些（子句全是硬編碼常數，使用者輸入一律走 params）
    conditions, params = [], []

    if keyword:
        conditions.append("(mrt = %s OR name LIKE %s)")   # 站名完全比對／景點名模糊比對
        params.append(keyword)
        params.append(f"%{keyword}%")

    if category:
        conditions.append("category = %s")
        params.append(category)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    with dict_cursor() as cursor:
        # 2. 多取一筆，判斷還有沒有下一頁
        cursor.execute(
            f"SELECT * FROM attractions {where} ORDER BY id LIMIT %s OFFSET %s",
            params + [PAGE_SIZE + 1, page * PAGE_SIZE],
        )
        rows = cursor.fetchall()

        if len(rows) > PAGE_SIZE:
            next_page = page + 1
            rows = rows[:PAGE_SIZE]
        else:
            next_page = None

        # 3. 一次撈完這頁所有景點的圖片
        img_map = fetch_images_for_ids(cursor, [r["id"] for r in rows])

    # 4. 組裝
    data = [normalize_attraction(r, img_map.get(r["id"], [])) for r in rows]

    return {"nextPage": next_page, "data": data}
