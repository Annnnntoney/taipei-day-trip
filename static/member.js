/* ============================================================
   Taipei Day Trip — 會員中心頁邏輯（Part 7-1）
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

/* ---------- DOM 元素 ---------- */
const memberNameEl = document.querySelector("#member-name");
const hostUrlEl    = document.querySelector("#host-url");
const tokenValueEl = document.querySelector("#token-value");
const generateBtn  = document.querySelector("#generate-btn");
const signoutBtn   = document.querySelector("#signout-btn");

/**
 * 頁面載入：確認登入狀態（沒登入導回首頁）→ 顯示名字、Host URL、現有金鑰。
 * 跟 booking 頁同一套流程，auth.js 的 window.Auth 已先掛好。
 */
async function init() {
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

    memberNameEl.textContent = result.data.name;

    // Host URL 用目前網域組出來：本機顯示 127.0.0.1、線上顯示正式網址，不用寫死
    hostUrlEl.textContent = `${location.origin}/mcp/`;

    loadToken();
  } catch (error) {
    console.error("登入狀態檢查失敗：", error);
    location.href = "/";
  }
}

/** 讀取目前的 MCP 金鑰；還沒產生過就維持 HTML 裡的提示文字。 */
async function loadToken() {
  try {
    const response = await fetch("/api/member/token", {
      headers: { "Authorization": `Bearer ${Auth.getToken()}` },
    });
    if (!response.ok) return;

    const result = await response.json();
    if (result.data) {
      tokenValueEl.textContent = result.data.token;
    }
  } catch (error) {
    console.error("讀取金鑰失敗：", error);
  }
}

/* Part 7-1：產生 / 更新金鑰——每按一次就換一把新的，舊金鑰立即作廢 */
generateBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/member/token", {
      method: "POST",
      headers: { "Authorization": `Bearer ${Auth.getToken()}` },
    });
    const result = await response.json();

    if (response.ok && result.data) {
      tokenValueEl.textContent = result.data.token;
    } else {
      tokenValueEl.textContent = "產生失敗，請稍後再試";
    }
  } catch (error) {
    console.error("產生金鑰失敗：", error);
    tokenValueEl.textContent = "連線失敗，請稍後再試";
  }
});

/* Part 7-1：登出會員（登出功能從導覽列搬到這裡） */
signoutBtn.addEventListener("click", () => {
  Auth.signOut();
  location.href = "/";
});

init();
