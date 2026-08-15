/* ============================================================
   Taipei Day Trip — 首頁邏輯
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

/* ---------- 全域狀態 ----------
   這三個變數是整份程式的核心，搜尋、無限捲動、捷運站篩選都共用          */
let nextPage = 0;        // 下一次要載入的頁碼；null 代表沒有下一頁了
let isLoading = false;   // 🔴 是否正在載入 —— 防止瞬間重複呼叫 API
let currentCategory = "";// 目前選取的分類；空字串代表不篩選
let currentKeyword = ""; // 目前的搜尋關鍵字

/* ---------- DOM 元素 ---------- */
const listEl        = document.querySelector("#attraction-list");
const statusEl      = document.querySelector("#status");
const sentinelEl    = document.querySelector("#sentinel");
const categoryBtn   = document.querySelector("#category-btn");
const categoryLabel = document.querySelector("#category-label");
const categoryMenu  = document.querySelector("#category-menu");
const searchInput   = document.querySelector("#search-input");
const searchBtn     = document.querySelector("#search-btn");
const mrtListEl     = document.querySelector("#mrt-list");
const mrtLeftBtn    = document.querySelector("#mrt-left");
const mrtRightBtn   = document.querySelector("#mrt-right");


/* ============================================================
   Part 2-2 / 2-3：載入景點並渲染
   ============================================================ */

/**
 * 載入下一頁景點。
 * 三個守衛缺一不可：正在載入、沒有下一頁、發生錯誤時要解鎖。
 */
async function loadNextPage() {
  if (isLoading) return;         // 🔴 正在載入 → 直接跳出，避免重複請求
  if (nextPage === null) return; // 已經沒有下一頁

  isLoading = true;              // 🔴 上鎖
  showStatus("載入中…");

  try {
    // URLSearchParams 會自動處理中文的 URL 編碼，不用自己 encodeURIComponent
    const params = new URLSearchParams({ page: nextPage });
    if (currentKeyword)  params.append("keyword", currentKeyword);
    if (currentCategory) params.append("category", currentCategory);

    const response = await fetch(`/api/attractions?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const result = await response.json();

    renderAttractions(result.data);
    nextPage = result.nextPage;  // 存回全域變數，供下一次載入使用

    // 三種狀態：查無結果 / 已載完全部 / 還有下一頁（不顯示提示）
    if (listEl.children.length === 0) {
      showStatus("找不到符合條件的景點");
    } else if (nextPage === null) {
      showStatus("已顯示全部景點");
    } else {
      hideStatus();
    }
  } catch (error) {
    console.error("載入景點失敗：", error);
    showStatus("載入失敗，請稍後再試");
  } finally {
    isLoading = false;           // 🔴 不論成功或失敗都要解鎖，否則之後永遠載不了
  }

  /* IntersectionObserver 只在「相交狀態改變」時觸發。
     若螢幕很高、8 張卡片填不滿一頁，哨兵會一直留在畫面內而不再觸發，
     無限捲動就卡住了。這裡主動補一次檢查。                              */
  if (isSentinelVisible()) loadNextPage();
}

/** 哨兵目前是否在視窗內（含 200px 的預載緩衝）。 */
function isSentinelVisible() {
  const rect = sentinelEl.getBoundingClientRect();
  return rect.top < window.innerHeight + 200;
}

/**
 * 把景點資料渲染成卡片，附加到列表底部。
 * 用 createElement + textContent 而不是 innerHTML —— 資料裡若含 HTML
 * 標籤不會被當程式碼執行（之後做會員留言功能時這是必要的習慣）。
 */
function renderAttractions(attractions) {
  for (const item of attractions) {
    const card = document.createElement("div");
    card.className = "card";

    // --- 圖片區（含名稱色帶）---
    const figure = document.createElement("div");
    figure.className = "card__figure";

    const img = document.createElement("img");
    img.className = "card__img";
    img.src = item.images[0];    // Guide 要求首頁只用第一張圖
    img.alt = item.name;
    img.loading = "lazy";        // 原生延遲載入，捲到才下載，省流量

    const name = document.createElement("p");
    name.className = "card__name";
    name.textContent = item.name;

    figure.append(img, name);

    // --- 資訊列（捷運站 / 分類）---
    const meta = document.createElement("div");
    meta.className = "card__meta";

    const mrt = document.createElement("span");
    mrt.className = "card__mrt";
    mrt.textContent = item.mrt || "";   // 有一筆景點沒有捷運站，會是 null

    const category = document.createElement("span");
    category.className = "card__category";
    category.textContent = item.category;

    meta.append(mrt, category);

    card.append(figure, meta);
    listEl.appendChild(card);
  }
}

function showStatus(text) { statusEl.textContent = text; statusEl.hidden = false; }
function hideStatus()     { statusEl.hidden = true; }


/* ============================================================
   Part 2-3：偵測捲到底 —— IntersectionObserver
   ============================================================ */

/**
 * 監看列表底部的「哨兵」元素。它一進入畫面就代表使用者捲到底了。
 * 比 scroll 事件好：瀏覽器原生最佳化、不會每秒觸發數十次。
 */
const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting) {
    loadNextPage();
  }
}, {
  rootMargin: "200px",   // 距離底部還有 200px 就先載入，捲動體驗更順
});

observer.observe(sentinelEl);


/* ============================================================
   Part 2-5：搜尋（分類 + 關鍵字）
   ============================================================ */

/**
 * 用目前的分類與關鍵字重新搜尋。
 * 🔴 兩件事一定要做：清空舊列表、把 nextPage 歸零。
 *    忘記清空 → 新舊資料混在一起
 *    忘記歸零 → 從中間的頁碼開始載
 */
function search() {
  currentKeyword = searchInput.value.trim();

  nextPage = 0;                  // 🔴 分頁狀態歸零
  listEl.innerHTML = "";         // 🔴 清空現有卡片
  hideStatus();

  loadNextPage();
}

searchBtn.addEventListener("click", search);

// 在輸入框按 Enter 也能搜尋（沒有用 <form>，所以不必 preventDefault）
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") search();
});


/* ============================================================
   Part 2-4：分類彈出面板
   ============================================================ */

/** 載入分類清單並建立面板選項。分類不會變，頁面載入時抓一次就好。 */
async function loadCategories() {
  try {
    const response = await fetch("/api/categories");
    const result = await response.json();

    // 第一個選項是「全部分類」，值為空字串 = 不篩選
    const options = ["全部分類", ...result.data];

    for (const name of options) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "category-menu__item";
      item.textContent = name;

      item.addEventListener("click", () => {
        // 「全部分類」對應空字串，其餘用分類名本身
        currentCategory = (name === "全部分類") ? "" : name;
        categoryLabel.textContent = name;

        // 更新選中樣式
        for (const el of categoryMenu.children) {
          el.classList.toggle("category-menu__item--active", el === item);
        }

        closeCategoryMenu();
        search();          // Guide 未強制，但選完立即篩選體驗較好
      });

      categoryMenu.appendChild(item);
    }
  } catch (error) {
    console.error("載入分類失敗：", error);
  }
}

function openCategoryMenu()  { categoryMenu.hidden = false; }
function closeCategoryMenu() { categoryMenu.hidden = true; }

categoryBtn.addEventListener("click", (event) => {
  event.stopPropagation();   // 避免事件冒泡到 document，剛開就被下面那段關掉
  categoryMenu.hidden ? openCategoryMenu() : closeCategoryMenu();
});

// 點面板以外的地方就關閉
document.addEventListener("click", (event) => {
  if (!categoryMenu.contains(event.target)) closeCategoryMenu();
});

// 按 Esc 關閉
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeCategoryMenu();
});


/* ============================================================
   Part 2-6：捷運站橫向列表
   ============================================================ */

/** 載入捷運站名稱（API 已依周邊景點數由多到少排序）。 */
async function loadMrts() {
  try {
    const response = await fetch("/api/mrts");
    const result = await response.json();

    for (const name of result.data) {
      const item = document.createElement("li");
      item.className = "mrt__item";
      item.textContent = name;

      item.addEventListener("click", () => {
        searchInput.value = name;   // Guide 2-6 要求：把站名填入搜尋框
        search();                   // 直接重用搜尋流程，不另寫一套篩選邏輯
      });

      mrtListEl.appendChild(item);
    }
  } catch (error) {
    console.error("載入捷運站失敗：", error);
  }
}

// 左右箭頭捲動；配合 CSS 的 scroll-behavior: smooth 就有動畫
const MRT_SCROLL_STEP = 300;
mrtLeftBtn.addEventListener("click",  () => { mrtListEl.scrollLeft -= MRT_SCROLL_STEP; });
mrtRightBtn.addEventListener("click", () => { mrtListEl.scrollLeft += MRT_SCROLL_STEP; });


/* ============================================================
   啟動
   ============================================================ */
loadCategories();
loadMrts();
loadNextPage();   // 載入第一頁景點（無篩選條件）
