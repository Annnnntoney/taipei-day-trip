from fastapi import *
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import contextlib
import datetime
import json
import os
import random
import secrets
import bcrypt
import jwt
import mysql.connector
import requests
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

# 會員中心頁（Part 7）——上面的 Static Pages 區塊規定不可修改，新頁面加在區塊外
@app.get("/member", include_in_schema=False)
async def member_page(request: Request):
	return FileResponse("./static/member.html", media_type="text/html")

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


def upsert_booking(member_id, attraction_id, date_str, time, price):
    """驗證輸入並建立（或覆蓋）預定行程。成功回 None，失敗回錯誤原因字串。
    網站的 POST /api/booking 和 Part 7 的 MCP add-to-cart tool 共用這一份邏輯。"""
    if time not in ("morning", "afternoon") or price not in (2000, 2500):
        return "輸入資料格式不正確"

    # 日期不能只信呼叫端：字串要真的是合法日期（否則進 DB 才爆會變 500），也不能是過去
    try:
        booking_date = datetime.date.fromisoformat(str(date_str))
    except (TypeError, ValueError):
        return "日期格式不正確"
    if booking_date < datetime.date.today():
        return "日期不可為過去的日期"

    with dict_cursor() as cursor:
        cursor.execute("SELECT id FROM attractions WHERE id = %s", (attraction_id,))
        if cursor.fetchone() is None:
            return "景點編號不存在"

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
            (member_id, attraction_id, booking_date, time, price),
        )

    return None


@app.post("/api/booking")
def create_booking(data: BookingInput, member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    error = upsert_booking(member["id"], data.attractionId, data.date, data.time, data.price)
    if error:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": f"建立失敗，{error}"},
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


# ---------------------------------------------------
# Order APIs (Part 6) — 建立訂單並用 TapPay 完成信用卡付款
# ---------------------------------------------------
TAPPAY_PARTNER_KEY = os.getenv("TAPPAY_PARTNER_KEY")
TAPPAY_MERCHANT_ID = os.getenv("TAPPAY_MERCHANT_ID")
TAPPAY_PAY_BY_PRIME_URL = "https://sandbox.tappaysdk.com/tpc/payment/pay-by-prime"


class OrderAttractionInput(BaseModel):
    id: int


class OrderTripInput(BaseModel):
    attraction: OrderAttractionInput
    date: str
    time: str


class OrderContactInput(BaseModel):
    name: str
    email: str
    phone: str


class OrderDetailInput(BaseModel):
    price: int
    trip: OrderTripInput
    contact: OrderContactInput


class OrderInput(BaseModel):
    prime: str
    order: OrderDetailInput


def generate_order_number():
    """時間戳記＋3 位亂數。直接讓人看得出下單時間，亂數只是降低撞號機率
    （真的撞號時 INSERT 會噴 IntegrityError，呼叫端要重試）。"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return timestamp + str(random.randint(100, 999))


def format_phone_for_tappay(phone):
    """TapPay 的 cardholder.phone_number 要求 E.164 格式（+886 開頭），
    使用者填的是台灣本地格式（0 開頭），這裡把開頭的 0 換成國碼。"""
    phone = phone.strip()
    return f"+886{phone[1:]}" if phone.startswith("0") else phone


def pay_by_prime(prime, amount, details, contact):
    """呼叫 TapPay Pay By Prime API，回傳 (status, message, rec_trade_id, bank_transaction_id)。
    連不上 TapPay（網路問題、API 回應不是 JSON）時視為付款失敗，不讓整支 Order API 噴 500——
    訂單本身仍要成功建立成 UNPAID，讓使用者之後有機會重新付款。"""
    try:
        response = requests.post(
            TAPPAY_PAY_BY_PRIME_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": TAPPAY_PARTNER_KEY,
            },
            json={
                "prime": prime,
                "partner_key": TAPPAY_PARTNER_KEY,
                "merchant_id": TAPPAY_MERCHANT_ID,
                "amount": amount,
                "currency": "TWD",
                "details": details,
                "cardholder": {
                    "phone_number": format_phone_for_tappay(contact["phone"]),
                    "name": contact["name"],
                    "email": contact["email"],
                },
                "remember": False,
            },
            timeout=10,
        )
        result = response.json()
        return (
            result.get("status", -1),
            result.get("msg", "付款失敗，請稍後再試"),
            result.get("rec_trade_id"),
            result.get("bank_transaction_id"),
        )
    except (requests.RequestException, ValueError):
        return (-1, "連線金流服務失敗，請稍後再試", None, None)


@app.post("/api/orders")
def create_order(data: OrderInput, member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    order = data.order

    # 1. 基本格式驗證（快速失敗）。注意：payload 只拿來「比對」，
    #    訂單真正寫入的內容一律以資料庫裡的預定行程為準（見交易一），防竄改
    try:
        order_date = datetime.date.fromisoformat(order.trip.date)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立訂單失敗，日期格式不正確"},
        )
    if order_date < datetime.date.today():
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立訂單失敗，日期不可為過去的日期"},
        )

    # 聯絡資訊不可為空，且長度不得超過資料表欄位上限——
    # 超長字串進到 INSERT 會噴資料庫錯誤變 500，該在這裡就用 400 擋下
    contact_name = order.contact.name.strip()
    contact_email = order.contact.email.strip()
    contact_phone = order.contact.phone.strip()
    if not contact_name or not contact_email or not contact_phone:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立訂單失敗，聯絡資訊不可為空"},
        )
    if len(contact_name) > 100 or len(contact_email) > 255 or len(contact_phone) > 20:
        return JSONResponse(
            status_code=400,
            content={"error": True, "message": "建立訂單失敗，聯絡資訊長度超過上限"},
        )

    # 2. 交易一：核對預定行程 → 原子認領 → 建立 UNPAID 訂單，先 commit 落地。
    #    交易一結束後不論後面發生什麼事（扣款失敗、程式掛掉），訂單都已存在
    with dict_cursor() as cursor:
        cursor.execute(
            "SELECT b.attraction_id, b.date, b.time, b.price, a.name "
            "FROM bookings b "
            "JOIN attractions a ON a.id = b.attraction_id "
            "WHERE b.member_id = %s",
            (member["id"],),
        )
        booking = cursor.fetchone()
        if booking is None:
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "建立訂單失敗，目前沒有預定行程"},
            )

        # payload 必須跟資料庫裡的預定行程完全一致，
        # 否則竄改 fetch body 就能用別的價格、別的景點付款
        if (
            order.trip.attraction.id != booking["attraction_id"]
            or order_date != booking["date"]
            or order.trip.time != booking["time"]
            or order.price != booking["price"]
        ):
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "建立訂單失敗，訂單內容與預定行程不符"},
            )

        # 原子認領：這條 DELETE 同時是「鎖」——兩個並發請求（另開分頁、連點、重送）
        # 只有一個刪得到列，另一個 rowcount=0 直接被擋，不會對同一筆預定重複扣款
        cursor.execute("DELETE FROM bookings WHERE member_id = %s", (member["id"],))
        if cursor.rowcount == 0:
            return JSONResponse(
                status_code=400,
                content={"error": True, "message": "訂單處理中，請勿重複送出"},
            )

        # 建立 UNPAID 訂單（值取自剛核對過的預定行程，不是 payload）。
        # number 是主鍵，理論上可能撞號，撞到就重新產生再試一次
        number = None
        for _ in range(5):
            candidate = generate_order_number()
            try:
                cursor.execute(
                    "INSERT INTO orders "
                    "(number, member_id, attraction_id, date, time, price, "
                    " contact_name, contact_email, contact_phone, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)",
                    (
                        candidate,
                        member["id"],
                        booking["attraction_id"],
                        booking["date"],
                        booking["time"],
                        booking["price"],
                        contact_name,
                        contact_email,
                        contact_phone,
                    ),
                )
                number = candidate
                break
            except mysql.connector.IntegrityError:
                continue
        if number is None:
            raise RuntimeError("無法產生不重複的訂單編號")

    # 3. 扣款。刻意放在兩個交易「之間」：外部 HTTP 呼叫不能夾在資料庫交易裡，
    #    否則整段扣款期間都佔著連線和鎖
    payment_status, payment_message, rec_trade_id, bank_transaction_id = pay_by_prime(
        prime=data.prime,
        amount=booking["price"],
        details=f"台北一日遊：{booking['name']}",
        contact={"name": contact_name, "email": contact_email, "phone": contact_phone},
    )

    # 4. 交易二：記錄付款結果。成功 → 訂單轉 PAID；
    #    失敗 → 把剛認領走的預定行程還回去，使用者才有機會重試
    try:
        with dict_cursor() as cursor:
            cursor.execute(
                "INSERT INTO order_payments "
                "(order_number, tappay_status, tappay_message, rec_trade_id, bank_transaction_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (number, payment_status, payment_message, rec_trade_id, bank_transaction_id),
            )
            if payment_status == 0:
                cursor.execute("UPDATE orders SET status = 1 WHERE number = %s", (number,))
            else:
                # INSERT IGNORE：若使用者在扣款期間已另建新預定，保留較新的那筆不覆蓋
                cursor.execute(
                    "INSERT IGNORE INTO bookings "
                    "(member_id, attraction_id, date, time, price) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        member["id"],
                        booking["attraction_id"],
                        booking["date"],
                        booking["time"],
                        booking["price"],
                    ),
                )
    except Exception:
        # 走到這裡代表「錢可能已扣、DB 卻沒記到」：把對帳線索留在 log。
        # 真實系統要做自動重試/退款/對帳；課程範圍內先保證 UNPAID 訂單已在交易一落地，
        # 可憑 rec_trade_id 到 TapPay 後台人工對帳
        print(f"[PAYMENT-RECONCILE] order={number} tappay_status={payment_status} rec_trade_id={rec_trade_id}")
        raise

    # 5. 規格：無論付款成功或失敗，都回傳訂單編號，讓前端導去感謝頁
    return {
        "data": {
            "number": number,
            "payment": {"status": payment_status, "message": payment_message},
        }
    }


@app.get("/api/order/{order_number}")
def get_order(order_number: str, member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    with dict_cursor() as cursor:
        # 只查自己名下的訂單：查得到別人的訂單編號也不該洩漏內容
        cursor.execute(
            "SELECT o.number, o.price, o.date, o.time, o.status, "
            "       o.contact_name, o.contact_email, o.contact_phone, "
            "       a.id AS attraction_id, a.name, a.address, "
            "       (SELECT url FROM attraction_images "
            "        WHERE attraction_id = a.id ORDER BY id LIMIT 1) AS image "
            "FROM orders o "
            "JOIN attractions a ON a.id = o.attraction_id "
            "WHERE o.number = %s AND o.member_id = %s",
            (order_number, member["id"]),
        )
        order = cursor.fetchone()

    if order is None:
        return {"data": None}

    return {
        "data": {
            "number": order["number"],
            "price": order["price"],
            "trip": {
                "attraction": {
                    "id": order["attraction_id"],
                    "name": order["name"],
                    "address": order["address"],
                    "image": order["image"],
                },
                "date": order["date"].isoformat(),
                "time": order["time"],
            },
            "contact": {
                "name": order["contact_name"],
                "email": order["contact_email"],
                "phone": order["contact_phone"],
            },
            "status": order["status"],
        }
    }


# ---------------------------------------------------
# Member MCP Token APIs (Part 7)
# 會員頁的「產生 / 更新金鑰」：發一把長期 API token 給 AI 工具（Codex）用。
# 跟網站登入用的 JWT 是兩套系統——JWT 會過期、內容自帶身分；
# 這把 token 是不透明字串，靠資料庫反查身分，可隨時重新產生讓舊的作廢
# ---------------------------------------------------
@app.get("/api/member/token")
def get_mcp_token(member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    with dict_cursor() as cursor:
        cursor.execute("SELECT token FROM mcp_tokens WHERE member_id = %s", (member["id"],))
        row = cursor.fetchone()

    return {"data": {"token": row["token"]} if row else None}


@app.post("/api/member/token")
def generate_mcp_token(member: dict = Depends(get_current_member)):
    unauthorized = require_member(member)
    if unauthorized:
        return unauthorized

    # secrets 模組是密碼學等級的亂數（random 模組可被預測，不能拿來當金鑰）
    token = secrets.token_hex(32)

    with dict_cursor() as cursor:
        # member_id 是主鍵：第一次 INSERT、之後同一人再按就 UPDATE 覆蓋，舊金鑰立即作廢
        cursor.execute(
            "INSERT INTO mcp_tokens (member_id, token) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE token = VALUES(token)",
            (member["id"], token),
        )

    return {"data": {"token": token}}


# ---------------------------------------------------
# MCP Server (Part 7) — 讓 AI 工具（Codex）透過 MCP 協定搜尋景點、建立預定
#
# MCP 的 Streamable HTTP 傳輸：客戶端把每一則 JSON-RPC 2.0 訊息 POST 到 /mcp/。
# 這裡走「無狀態」模式（不發 session id、直接回 application/json），
# 規範允許，實作最單純。要處理的方法只有四種：
#   initialize（握手）→ notifications/initialized（通知，回 202 即可）
#   → tools/list（列出工具）→ tools/call（呼叫工具）
# ---------------------------------------------------
MCP_TOOLS = [
    {
        # 🔴 name 只能用英數/底線：Codex 會把 MCP tool 對應到 OpenAI 的 function calling，
        # function 名稱不接受中文。規格書要求的中文名稱放在 title 與 description
        "name": "search_attractions",
        "title": "搜尋台北市景點",
        "description": "透過關鍵字和捷運站名搜尋台北市一日旅遊的景點",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "景點名稱關鍵字（模糊比對）或捷運站名（完全比對）",
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "add_to_cart",
        "title": "預定景點導覽行程",
        "description": "根據景點編號、日期、時間、價格，預定一個景點導覽行程",
        "inputSchema": {
            "type": "object",
            "properties": {
                "attractionId": {"type": "integer", "description": "景點編號"},
                "date": {"type": "string", "description": "導覽日期，格式 YYYY-MM-DD，不可為過去日期"},
                "time": {
                    "type": "string",
                    "enum": ["morning", "afternoon"],
                    "description": "時段：morning＝上半天、afternoon＝下半天",
                },
                "price": {
                    "type": "integer",
                    "enum": [2000, 2500],
                    "description": "費用：上半天 2000、下半天 2500",
                },
            },
            "required": ["attractionId", "date", "time", "price"],
        },
    },
]


def get_member_id_by_mcp_token(authorization):
    """用 Authorization 標頭裡的 MCP token 反查會員 id；查不到（token 無效）回 None。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):].strip()
    if not token:
        return None

    with dict_cursor() as cursor:
        cursor.execute("SELECT member_id FROM mcp_tokens WHERE token = %s", (token,))
        row = cursor.fetchone()

    return row["member_id"] if row else None


def mcp_search_attractions(keyword):
    """search tool 本體：比照網站搜尋（站名完全比對／景點名模糊比對），不分頁。
    description 是「簡介」，截前 80 字就夠 AI 判斷，也讓回應不要肥到拖慢對話。"""
    with dict_cursor() as cursor:
        cursor.execute(
            "SELECT id, name, description, category, mrt FROM attractions "
            "WHERE mrt = %s OR name LIKE %s "
            "ORDER BY id",
            (keyword, f"%{keyword}%"),
        )
        rows = cursor.fetchall()

    return {
        "data": [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"][:80],
                "category": row["category"],
                "mrt": row["mrt"],
            }
            for row in rows
        ]
    }


def mcp_tool_text(payload):
    """MCP tools/call 的回傳格式：結果包成一段 text content，內容是規格書要求的 JSON 字串。"""
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": False,
    }


def jsonrpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


@app.post("/mcp/")
@app.post("/mcp", include_in_schema=False)   # 有沒有結尾斜線都收，設定檔少打一撇不至於整個掛掉
async def mcp_endpoint(request: Request, authorization: str = Header(None)):
    try:
        message = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=jsonrpc_error(None, -32700, "Parse error"))

    if not isinstance(message, dict):
        return JSONResponse(status_code=400, content=jsonrpc_error(None, -32600, "Invalid request"))

    # 沒有 id 的訊息是「通知」（例如 notifications/initialized）：
    # 依 Streamable HTTP 規範回 202 Accepted、不帶內容
    if "id" not in message:
        return Response(status_code=202)

    msg_id = message["id"]
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        result = {
            # 客戶端提議它要的協定版本，支援的話照樣回去（我們的功能面各版本都相容）
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "台北一日遊", "version": "1.0.0"},
        }

    elif method == "ping":
        result = {}

    elif method == "tools/list":
        result = {"tools": MCP_TOOLS}

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments") or {}

        if tool_name == "search_attractions":
            # 規格：工具執行出錯回 {"error": true}，不是讓整個請求 500
            try:
                keyword = str(args.get("keyword", "")).strip()
                # 🔴 空字串沒擋掉的話，SQL 的 LIKE '%%' 會比對到每一筆，
                # 等於把整個景點目錄倒出去，不是規格要的「錯誤」
                if not keyword:
                    payload = {"error": True}
                else:
                    payload = mcp_search_attractions(keyword)
            except Exception:
                payload = {"error": True}
            result = mcp_tool_text(payload)

        elif tool_name == "add_to_cart":
            # 規格：先用 token 反查會員，查不到就是無效 token；
            # 查到了就跟網站上已登入會員建立預定完全一樣（共用 upsert_booking）
            try:
                member_id = get_member_id_by_mcp_token(authorization)
                if member_id is None:
                    payload = {"error": True}
                else:
                    error = upsert_booking(
                        member_id,
                        args.get("attractionId"),
                        args.get("date"),
                        args.get("time"),
                        args.get("price"),
                    )
                    if error:
                        payload = {"error": True}
                    else:
                        booking_url = str(request.base_url).rstrip("/") + "/booking"
                        payload = {
                            "ok": True,
                            "message": f"台北導覽行程，預定成功，請到 {booking_url} 完成付款。",
                        }
            except Exception:
                payload = {"error": True}
            result = mcp_tool_text(payload)

        else:
            return jsonrpc_error(msg_id, -32602, f"Unknown tool: {tool_name}")

    else:
        return jsonrpc_error(msg_id, -32601, f"Method not found: {method}")

    return {"jsonrpc": "2.0", "id": msg_id, "result": result}
