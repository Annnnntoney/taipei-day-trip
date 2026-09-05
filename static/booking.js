/* ============================================================
   Taipei Day Trip — 預定行程頁邏輯（Part 5-5）
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

const TIME_LABEL = { morning: "上半天", afternoon: "下半天" };

/* ---------- DOM 元素 ---------- */
const emptyMessage = document.querySelector("#empty-message");
const bookingCard  = document.querySelector("#booking-card");
const imageEl      = document.querySelector("#booking-image");
const nameEl       = document.querySelector("#booking-name");
const addressEl    = document.querySelector("#booking-address");
const dateEl       = document.querySelector("#booking-date");
const timeEl       = document.querySelector("#booking-time");
const priceEl      = document.querySelector("#booking-price");
const deleteBtn    = document.querySelector("#delete-btn");

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
    const result = await response.json();
    render(result.data);
  } catch (error) {
    console.error("載入預定行程失敗：", error);
  }
}

/** data 為 null 代表沒有預定行程；否則依 API 回應把資料填進畫面。 */
function render(booking) {
  if (!booking) {
    emptyMessage.hidden = false;
    bookingCard.hidden = true;
    return;
  }

  emptyMessage.hidden = true;
  bookingCard.hidden = false;

  imageEl.src = booking.attraction.image;
  imageEl.alt = booking.attraction.name;
  nameEl.textContent = booking.attraction.name;
  addressEl.textContent = booking.attraction.address;
  dateEl.textContent = booking.date;
  timeEl.textContent = TIME_LABEL[booking.time];
  priceEl.textContent = `新台幣 ${booking.price} 元`;
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
