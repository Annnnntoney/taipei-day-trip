/* ============================================================
   Taipei Day Trip — 感謝頁邏輯（Part 6-4, 6-5）
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

const TIME_LABEL = {
  morning: "早上 9 點到下午 4 點",
  afternoon: "下午 2 點到晚上 9 點",
};

const STATUS_LABEL = {
  0: "尚未成功付款，請重新確認信用卡資訊或聯繫客服",
  1: "付款成功",
};

/** Part 6-5：從 query string 取出訂單編號，例如 /thankyou?number=20260910120000123 */
function getOrderNumber() {
  return new URLSearchParams(location.search).get("number");
}

const orderNumber   = getOrderNumber();
const titleEl       = document.querySelector("#thankyou-title");
const numberEl      = document.querySelector("#order-number");
const detailEl      = document.querySelector("#order-detail");
const attractionEl  = document.querySelector("#order-attraction");
const dateEl        = document.querySelector("#order-date");
const timeEl        = document.querySelector("#order-time");
const priceEl       = document.querySelector("#order-price");
const statusEl      = document.querySelector("#order-status");

async function loadOrder() {
  // 網址沒帶訂單編號（例如直接打開 /thankyou）：只改標題，不視為錯誤讓整頁掛掉
  if (!orderNumber) {
    titleEl.textContent = "找不到訂單編號";
    return;
  }
  numberEl.textContent = orderNumber;

  // 這頁允許沒登入也能看到訂單編號（分享/重新整理都不該把人擋在外面），
  // 只有「查詳細內容」這個加分功能才需要 token
  const token = Auth.getToken();
  if (!token) return;

  try {
    const response = await fetch(`/api/order/${orderNumber}`, {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) return;

    const result = await response.json();
    if (result.data) render(result.data);
  } catch (error) {
    console.error("載入訂單詳情失敗：", error);   // 查不到細節就維持只顯示訂單編號
  }
}

function render(order) {
  detailEl.hidden = false;
  attractionEl.textContent = order.trip.attraction.name;
  dateEl.textContent = order.trip.date;
  timeEl.textContent = TIME_LABEL[order.trip.time];
  priceEl.textContent = `新台幣 ${order.price} 元`;
  statusEl.textContent = STATUS_LABEL[order.status];
}

loadOrder();
