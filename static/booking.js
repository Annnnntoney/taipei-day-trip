/* ============================================================
   Taipei Day Trip — 預定行程頁邏輯（Part 5-5）
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

/* Figma 的時間顯示格式是完整時段（demo 內容為上半天「早上 9 點到下午 4 點」）*/
const TIME_LABEL = {
  morning: "早上 9 點到下午 4 點",
  afternoon: "下午 2 點到晚上 9 點",
};

/* ---------- DOM 元素 ---------- */
const memberNameEl   = document.querySelector("#member-name");
const emptyMessage   = document.querySelector("#empty-message");
const bookingContent = document.querySelector("#booking-content");
const imageEl        = document.querySelector("#booking-image");
const nameEl         = document.querySelector("#booking-name");
const dateEl         = document.querySelector("#booking-date");
const timeEl         = document.querySelector("#booking-time");
const priceEl        = document.querySelector("#booking-price");
const addressEl      = document.querySelector("#booking-address");
const totalPriceEl   = document.querySelector("#total-price");
const contactNameEl  = document.querySelector("#contact-name");
const contactEmailEl = document.querySelector("#contact-email");
const contactPhoneEl = document.querySelector("#contact-phone");
const deleteBtn      = document.querySelector("#delete-btn");
const confirmBtn     = document.querySelector("#confirm-btn");
const orderMessage   = document.querySelector("#order-message");

let currentUser = null;      // 登入會員資料，渲染問候語與聯絡資訊用
let currentBooking = null;   // 目前這筆預定行程，建立訂單時要用（景點 id、日期、時間、價格）

/**
 * Part 5-5 步驟 1：先確認登入狀態，沒登入就導回首頁。
 * auth.js 已經先掛好 window.Auth，這裡直接用它拿 token，不重複寫一份 localStorage 邏輯。
 */
async function checkSignedInThenLoad() {
  const token = Auth.getToken();
  if (!token) {
    location.href = "/";
    return;
  }

  try {
    const response = await fetch("/api/user/auth", {
      headers: { "Authorization": `Bearer ${token}` },
    });
    const result = await response.json();

    if (!result.data) {
      location.href = "/";
      return;
    }

    currentUser = result.data;
    memberNameEl.textContent = currentUser.name;

    loadBooking();
  } catch (error) {
    console.error("登入狀態檢查失敗：", error);
    location.href = "/";
  }
}

/** Part 5-5 步驟 2：取得預定行程資料並渲染。 */
async function loadBooking() {
  try {
    const response = await fetch("/api/booking", {
      headers: { "Authorization": `Bearer ${Auth.getToken()}` },
    });

    // 🔴 500/403 的回應沒有 data 欄位，不檢查就渲染會把「伺服器壞了」顯示成「沒有行程」
    if (!response.ok) {
      showLoadError();
      return;
    }

    const result = await response.json();
    render(result.data);
  } catch (error) {
    console.error("載入預定行程失敗：", error);
    showLoadError();
  }
}

/** 載入失敗：借用空狀態的位置顯示錯誤訊息，跟「沒有行程」區分開。 */
function showLoadError() {
  emptyMessage.textContent = "載入失敗，請稍後再試";
  emptyMessage.hidden = false;
  bookingContent.hidden = true;
}

/** data 為 null 代表沒有預定行程；否則依 API 回應把資料填進畫面。 */
function render(booking) {
  if (!booking) {
    emptyMessage.hidden = false;
    bookingContent.hidden = true;
    return;
  }

  emptyMessage.hidden = true;
  bookingContent.hidden = false;
  currentBooking = booking;

  imageEl.src = booking.attraction.image;
  imageEl.alt = booking.attraction.name;
  nameEl.textContent = `台北一日遊：${booking.attraction.name}`;   // Figma 格式
  dateEl.textContent = booking.date;
  timeEl.textContent = TIME_LABEL[booking.time];
  priceEl.textContent = `新台幣 ${booking.price} 元`;
  addressEl.textContent = booking.attraction.address;
  totalPriceEl.textContent = `新台幣 ${booking.price} 元`;

  // 聯絡資訊帶入登入會員的姓名／email（Figma 設計是已填好的輸入框）
  contactNameEl.value = currentUser.name;
  contactEmailEl.value = currentUser.email;
}

/** Part 5-5 步驟 3：刪除預定行程，成功後重新整理頁面。 */
deleteBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/booking", {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${Auth.getToken()}` },
    });
    const result = await response.json();

    if (result.ok) {
      location.reload();
    }
  } catch (error) {
    console.error("刪除預定行程失敗：", error);
  }
});

checkSignedInThenLoad();

/* ============================================================
   Part 6-2：TapPay 信用卡輸入（前端流程）
   ⚠️ 換成你自己 TapPay 帳號（sandbox）的 App ID / App Key，見 PART6_STEP_BY_STEP.md 步驟 1
   ============================================================ */
const TAPPAY_APP_ID = 171166;
const TAPPAY_APP_KEY = "app_p774Jm5hRzcqaM4NkR2rWQK3wUPVIhdhDdn2TDjxekKd8pft2Nev1jcmeju6";

TPDirect.setupSDK(TAPPAY_APP_ID, TAPPAY_APP_KEY, "sandbox");

TPDirect.card.setup({
  fields: {
    number: { element: "#card-number", placeholder: "**** **** **** ****" },
    expirationDate: { element: "#card-expiry", placeholder: "MM / YY" },
    ccv: { element: "#card-cvv", placeholder: "CVV" },
  },
  styles: {
    input: { color: "#000000", "font-size": "16px", "font-family": "inherit" },
    ":focus": { color: "#448899" },
    ".valid": { color: "#2E8B57" },
    ".invalid": { color: "#D0021B" },
  },
});

/* ============================================================
   Part 6-3：建立訂單並付款
   ============================================================ */
confirmBtn.addEventListener("click", () => {
  orderMessage.textContent = "";

  if (!currentBooking) return;   // 沒有預定行程時按鈕本來就不會被看到，防呆用

  const name = contactNameEl.value.trim();
  const email = contactEmailEl.value.trim();
  const phone = contactPhoneEl.value.trim();
  if (!name || !email || !phone) {
    orderMessage.textContent = "請填寫完整的聯絡資訊";
    return;
  }

  // 送出前先問 TapPay 卡片欄位有沒有填完整、格式對不對，不必等 getPrime 才知道
  const cardStatus = TPDirect.card.getTappayFieldsStatus();
  if (!cardStatus.canGetPrime) {
    orderMessage.textContent = "請確認信用卡資訊填寫正確";
    return;
  }

  confirmBtn.disabled = true;

  // 透過 TapPay SDK 把卡片資訊換成 prime；前端全程拿不到卡號明碼
  TPDirect.card.getPrime(async (result) => {
    if (result.status !== 0) {
      orderMessage.textContent = "信用卡資訊有誤，請重新確認";
      confirmBtn.disabled = false;
      return;
    }

    try {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${Auth.getToken()}`,
        },
        body: JSON.stringify({
          prime: result.card.prime,
          order: {
            price: currentBooking.price,
            trip: {
              attraction: { id: currentBooking.attraction.id },
              date: currentBooking.date,
              time: currentBooking.time,
            },
            contact: { name, email, phone },
          },
        }),
      });
      const resBody = await response.json();

      if (response.ok && resBody.data) {
        // 規格：不論這次付款成功或失敗，Order API 都會回傳訂單編號，一律導去感謝頁
        location.href = `/thankyou?number=${resBody.data.number}`;
      } else {
        orderMessage.textContent = resBody.message || "訂購失敗，請稍後再試";
        confirmBtn.disabled = false;
      }
    } catch (error) {
      console.error("建立訂單失敗：", error);
      orderMessage.textContent = "連線失敗，請稍後再試";
      confirmBtn.disabled = false;
    }
  });
});
