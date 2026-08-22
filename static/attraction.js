/* ============================================================
   Taipei Day Trip — 景點頁邏輯
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

/**
 * 從網址 /attraction/10 取出景點編號。
 * "/attraction/10".split("/") → ["", "attraction", "10"]
 *                                 ↑0      ↑1         ↑2
 * 取不到或不是純數字時回傳 null。
 */
function getAttractionId() {
  const id = location.pathname.split("/")[2];
  return /^\d+$/.test(id) ? id : null;
}

const ATTRACTION_ID = getAttractionId();

/* ---------- DOM 元素 ---------- */
const nameEl        = document.querySelector("#name");
const categoryEl    = document.querySelector("#category");
const mrtEl         = document.querySelector("#mrt");
const descriptionEl = document.querySelector("#description");
const addressEl     = document.querySelector("#address");
const transportEl   = document.querySelector("#transport");
const bookingForm   = document.querySelector("#booking-form");

/** 載入景點資料。 */
async function loadAttraction() {
  // 網址裡的 id 不合法（例如 /attraction/abc）
  if (ATTRACTION_ID === null) {
    showError("網址不正確");
    return;
  }

  try {
    const response = await fetch(`/api/attraction/${ATTRACTION_ID}`);

    // 🔴 fetch 只有「連不上」才會失敗；HTTP 400 / 500 都算成功回應，要自己檢查
    if (!response.ok) {
      showError("找不到這個景點");
      return;
    }

    const result = await response.json();
    render(result.data);
  } catch (error) {
    console.error("載入景點失敗：", error);
    showError("載入失敗，請稍後再試");
  }
}

/** 把資料填進畫面。用 textContent 不用 innerHTML，資料含 HTML 也不會被執行。 */
function render(data) {
  nameEl.textContent        = data.name;
  categoryEl.textContent    = data.category;
  mrtEl.textContent         = data.mrt || "";          // 🔴 有景點的 mrt 是 null
  descriptionEl.textContent = data.description;
  addressEl.textContent     = data.address;
  transportEl.textContent   = data.transport || "";

  document.title = `${data.name} - 台北一日遊`;   // 分頁標籤顯示景點名稱

  setupSlideshow(data.images);
}

/** 出錯時：標題顯示訊息、把預訂表單藏起來。 */
function showError(message) {
  nameEl.textContent = message;
  bookingForm.hidden = true;
}

loadAttraction();

/* ============================================================
   Guide 3-5：圖片輪播
   核心觀念：狀態（currentIndex）→ 畫面（renderSlideshow）
   ============================================================ */

const trackEl = document.querySelector("#slide-track");
const dotsEl  = document.querySelector("#slide-dots");
const prevBtn = document.querySelector("#slide-prev");
const nextBtn = document.querySelector("#slide-next");

let currentIndex = 0;
let totalSlides = 0;

/** 依 images 陣列產生圖片與指示段（數量不寫死，由資料決定）。 */
function setupSlideshow(images) {
  totalSlides = images.length;

  // 只有一張圖時，箭頭和指示條都沒有意義 → 藏起來
  if (totalSlides <= 1) {
    prevBtn.hidden = true;
    nextBtn.hidden = true;
  }

  for (let i = 0; i < totalSlides; i++) {
    // --- 圖片 ---
    const slide = document.createElement("div");
    slide.className = "slideshow__slide";

    const img = document.createElement("img");
    img.src = images[i];
    img.alt = "";                          // 純裝飾圖，旁邊已有景點名稱標題
    if (i > 0) img.loading = "lazy";       // 第一張立刻載，其餘切到再載
    slide.appendChild(img);
    trackEl.appendChild(slide);

    // --- 指示段 ---
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "slideshow__dot";
    dot.setAttribute("aria-label", `第 ${i + 1} 張圖片`);
    dot.addEventListener("click", () => goTo(i));
    dotsEl.appendChild(dot);
  }

  renderSlideshow();
}

/** 🔴 唯一負責「把狀態畫到畫面上」的函式，所有切換最後都走這裡。 */
function renderSlideshow() {
  // ① 移動整條 track
  trackEl.style.transform = `translateX(-${currentIndex * 100}%)`;

  // ② 更新指示段樣式
  for (let i = 0; i < dotsEl.children.length; i++) {
    dotsEl.children[i].classList.toggle("slideshow__dot--active", i === currentIndex);
  }
}

function goTo(index) {
  currentIndex = index;
  renderSlideshow();
}

// 🔴 事件監聽只綁一次（不放在 setupSlideshow 裡，職責分開）
// +totalSlides 再 % 是為了讓 -1 變成最後一張 → 頭尾循環
prevBtn.addEventListener("click", () => goTo((currentIndex - 1 + totalSlides) % totalSlides));
nextBtn.addEventListener("click", () => goTo((currentIndex + 1) % totalSlides));

/* ============================================================
   Guide 3-3：時間選擇 → 價格
   ============================================================ */

const PRICE = { morning: 2000, afternoon: 2500 };   // 數字集中一處，要改只改這行

const priceEl = document.querySelector("#price");

function updatePrice() {
  // <form> 可以用「表單.欄位name」直接取值；radio 群組取到的是被選中那顆的 value
  const time = bookingForm.time.value;      // "morning" 或 "afternoon"
  priceEl.textContent = `新台幣 ${PRICE[time]} 元`;
}

// 用 change 不用 click：鍵盤方向鍵切換也會觸發
bookingForm.addEventListener("change", updatePrice);

// 🔴 載入時先算一次，否則使用者沒點過任何東西時價格是 HTML 寫死的字
updatePrice();

// 目前還沒有預訂功能（Part 4 才做），先擋掉送出時的重新整理
bookingForm.addEventListener("submit", (event) => {
  event.preventDefault();
});

// 日期不能選過去。⚠️ 不用 toISOString()，它會轉 UTC，早上 8 點前會少一天
const dateEl = document.querySelector("#date");
const today = new Date();
const yyyy = today.getFullYear();
const mm = String(today.getMonth() + 1).padStart(2, "0");   // 月份從 0 開始要 +1
const dd = String(today.getDate()).padStart(2, "0");
dateEl.min = `${yyyy}-${mm}-${dd}`;