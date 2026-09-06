from fastapi import *
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import contextlib
import datetime
import os
import bcrypt
import jwt
import mysql.connector
from dotenv import load_dotenv


app=FastAPI()
load_dotenv()

# Static Pages (Never Modify Code in this Block)
@app.get("/", include_in_schema=False)
async def index(request: Request):
	return FileResponse("./static/index.html", media_type="text/html")

@app.get("/attraction/{id}", include_in_schema=False)
async def attraction(request: Request, id: str):
	# id 收 str 不收 int：/attraction/abc 也要回這張頁面，
	# 讓前端顯示「網址不正確」；宣告 int 會被 FastAPI 直接 422 擋掉，前端邏輯永遠跑不到
	return FileResponse("./static/attraction.html", media_type="text/html")

@app.get("/booking", include_in_schema=False)
async def booking(request: Request):
	return FileResponse("./static/booking.html", media_type="text/html")

@app.get("/thankyou", include_in_schema=False)
async def thankyou(request: Request):
	return FileResponse("./static/thankyou.html", media_type="text/html")

# ---------------------------------------------------
# Static assets (CSS / JS / images)
# 掛載後 static/style.css 自動對應到 /static/style.css，新增檔案不用改程式
# ---------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")


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
        conn.commit()   # 🔴 connector 預設不自動提交：沒這行，INSERT 會在關閉連線時被回滾
    finally:            # 出錯時跳過 commit，close 會自動回滾，資料不會寫一半
        cursor.close()
        conn.close()


def fetch_images_for_ids(cursor, ids):
    """Fetch every image of the given attractions in one query, grouped by id."""
    if not ids:
        return {}
    # SQL 為純靜態字串：固定 PAGE_SIZE 個佔位符，不足的用 None 補滿
    # （IN 清單裡的 NULL 永遠不會比對到任何列，無副作用）
    padded = list(ids) + [None] * (PAGE_SIZE - len(ids))
    cursor.execute(
        "SELECT attraction_id, url FROM attraction_images "
        "WHERE attraction_id IN (%s, %s, %s, %s, %s, %s, %s, %s)",
        padded,
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
# User APIs (Part 4)
# ---------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRE_DAYS = 7


# 請求 body 的格式宣告：FastAPI 會自動解析 JSON 並檢查欄位存在，
# 缺欄位或不是 JSON 時直接回 422，不會進到函式裡
class SignUpInput(BaseModel):
    name: str
    email: str
    password: str


class SignInInput(BaseModel):
    email: str
    password: str


# 任何沒被接住的例外（DB 斷線等）統一回規格書要求的 500 格式，
# 而不是 FastAPI 預設的 {"detail": "Internal Server Error"}
@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "伺服器內部錯誤"},
    )


@app.post("/api/user")
def sign_up(data: SignUpInput):
    # 1. 基本驗證：strip 後為空視同沒填（BaseModel 只擋「缺欄位」，擋不了空字串）
    name = data.name.strip()
    email = data.email.strip()
    if not name or not email or not data.password:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "註冊失敗，姓名、Email 與密碼皆不可為空"},
        )

    # 2. 密碼雜湊後才進資料庫：資料庫被偷走也拿不到明文密碼
    hashed = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # 3. 直接 INSERT，靠資料表的 UNIQUE(email) 擋重複——
    #    先 SELECT 再 INSERT 有時間差（race condition），交給資料庫判斷才可靠
    try:
        with dict_cursor() as cursor:
            cursor.execute(
                "INSERT INTO members (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed),
            )
    except mysql.connector.IntegrityError:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "註冊失敗，這個 Email 已經被註冊"},
        )

    return {"ok": True}


@app.put("/api/user/auth")
def sign_in(data: SignInInput):
    # 1. 用 email 找會員
    with dict_cursor() as cursor:
        cursor.execute(
            "SELECT id, name, email, password FROM members WHERE email = %s",
            (data.email.strip(),),
        )
        member = cursor.fetchone()

    # 2. 「查無此人」和「密碼錯誤」回同一句話：不讓人試探哪些 email 有註冊過
    if member is None or not bcrypt.checkpw(
        data.password.encode("utf-8"), member["password"].encode("utf-8")
    ):
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "登入失敗，Email 或密碼錯誤"},
        )

    # 3. 簽發 token：exp 讓 token 七天後自動失效，PyJWT 解碼時會自動檢查
    payload = {
        "id": member["id"],
        "name": member["name"],
        "email": member["email"],
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=JWT_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"token": token}


def get_current_member(authorization: str = Header(None)):
    """解出目前登入的會員 payload；沒登入或 token 無效一律回 None，交給呼叫端決定怎麼回應。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[len("Bearer "):]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:  # 涵蓋過期、被竄改、格式錯誤
        return None


@app.get("/api/user/auth")
def get_auth(member: dict = Depends(get_current_member)):
    # 依規格：沒登入（沒帶 token、token 壞掉或過期）一律回 {"data": null}，不是錯誤
    if member is None:
        return {"data": None}

    return {"data": {"id": member["id"], "name": member["name"], "email": member["email"]}}


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
    # 1. 條件參數化：參數為 NULL 時該組條件恆真＝不做篩選，SQL 本身是純靜態字串
    like = f"%{keyword}%" if keyword else None

    with dict_cursor() as cursor:
        # 2. 多取一筆，判斷還有沒有下一頁
        cursor.execute(
            "SELECT * FROM attractions "
            "WHERE (%s IS NULL OR mrt = %s OR name LIKE %s) "   # 站名完全比對／景點名模糊比對
            "  AND (%s IS NULL OR category = %s) "
            "ORDER BY id LIMIT %s OFFSET %s",
            (keyword, keyword, like, category, category, PAGE_SIZE + 1, page * PAGE_SIZE),
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


# ---------------------------------------------------
# Booking APIs (Part 5)
# 3 支都需要授權：未登入一律回 403，跟規格書一致
# ---------------------------------------------------
class BookingInput(BaseModel):
    attractionId: int
    date: str
    time: str
    price: int


def require_member(member):
    """三支 Booking API 共用的授權檢查；沒登入直接回規格書要求的 403。"""
    if member is None:
        return JSONResponse(
            status_code=403,
            content={"error": True, "message": "請先登入會員"},
        )
    return None


@app.get("/api/booking")
def get_booking(member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    with dict_cursor() as cursor:
        # 一個會員最多一筆預定行程，JOIN 景點取顯示用的名稱/地址，子查詢取第一張圖
        cursor.execute(
            "SELECT b.date, b.time, b.price, "
            "       a.id AS attraction_id, a.name, a.address, "
            "       (SELECT url FROM attraction_images "
            "        WHERE attraction_id = a.id ORDER BY id LIMIT 1) AS image "
            "FROM bookings b "
            "JOIN attractions a ON a.id = b.attraction_id "
            "WHERE b.member_id = %s",
            (member["id"],),
        )
        booking = cursor.fetchone()

    if booking is None:
        return {"data": None}

    return {
        "data": {
            "attraction": {
                "id": booking["attraction_id"],
                "name": booking["name"],
                "address": booking["address"],
                "image": booking["image"],
            },
            "date": booking["date"].isoformat(),   # DATE 欄位是 date 物件，不是 JSON serializable
            "time": booking["time"],
            "price": booking["price"],
        }
    }


@app.post("/api/booking")
def create_booking(data: BookingInput, member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    if data.time not in ("morning", "afternoon") or data.price not in (2000, 2500):
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立失敗，輸入資料格式不正確"},
        )

    # 日期不能只信前端：字串要真的是合法日期（否則進 DB 才爆會變 500），也不能是過去
    try:
        booking_date = datetime.date.fromisoformat(data.date)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立失敗，日期格式不正確"},
        )
    if booking_date < datetime.date.today():
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立失敗，日期不可為過去的日期"},
        )

    with dict_cursor() as cursor:
        cursor.execute("SELECT id FROM attractions WHERE id = %s", (data.attractionId,))
        if cursor.fetchone() is None:
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "建立失敗，景點編號不存在"},
            )

        # 每位會員同時只能有一筆預定行程（bookings.member_id 有 UNIQUE）：
        # 已存在就直接覆蓋成新的一筆，不用先查再決定 INSERT 還是 UPDATE
        cursor.execute(
            "INSERT INTO bookings (member_id, attraction_id, date, time, price) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "  attraction_id = VALUES(attraction_id), "
            "  date = VALUES(date), "
            "  time = VALUES(time), "
            "  price = VALUES(price)",
            (member["id"], data.attractionId, booking_date, data.time, data.price),
        )

    return {"ok": True}


@app.delete("/api/booking")
def delete_booking(member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    with dict_cursor() as cursor:
        cursor.execute("DELETE FROM bookings WHERE member_id = %s", (member["id"],))

    return {"ok": True}
