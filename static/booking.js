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
const deleteBtn      = document.querySelector("#delete-btn");

let currentUser = null;   // 登入會員資料，渲染問候語與聯絡資訊用

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
