/* ============================================================
   Taipei Day Trip — 會員系統（Part 4）
   所有頁面共用：登入狀態檢查、登入/註冊彈窗、登出
   規定：不得使用任何第三方函式庫，只用瀏覽器原生 API
   ============================================================ */

/* ---------- 常數 ----------
   token 存 localStorage 的 key 名稱集中管理，打錯字只會錯在一個地方 */
const TOKEN_KEY = "token";

/* ============================================================
   彈窗 HTML：由 JS 注入 <body>
   （首頁、景點頁共用同一份，改一次兩頁都生效）
   ============================================================ */
document.body.insertAdjacentHTML("beforeend", `
  <div class="dialog-overlay" id="auth-overlay" hidden>
    <div class="dialog" role="dialog" aria-modal="true">
      <div class="dialog__bar"></div>
      <button type="button" class="dialog__close" id="auth-close" aria-label="關閉">
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path fill="none" stroke="#666" stroke-width="2.5" stroke-linecap="round"
                d="M5 5 19 19M19 5 5 19"/>
        </svg>
      </button>

      <!-- 登入表單（預設顯示） -->
      <form class="dialog__form" id="signin-form">
        <h2 class="dialog__title">登入會員帳號</h2>
        <input class="dialog__input" type="email" name="email" placeholder="輸入電子信箱" required>
        <input class="dialog__input" type="password" name="password" placeholder="輸入密碼" required>
        <button type="submit" class="dialog__submit">登入帳戶</button>
        <p class="dialog__message" id="signin-message"></p>
        <p class="dialog__switch">還沒有帳戶？<span class="dialog__link" id="to-signup">點此註冊</span></p>
      </form>

      <!-- 註冊表單（點「點此註冊」才顯示） -->
      <form class="dialog__form" id="signup-form" hidden>
        <h2 class="dialog__title">註冊會員帳號</h2>
        <input class="dialog__input" type="text" name="name" placeholder="輸入姓名" required>
        <input class="dialog__input" type="email" name="email" placeholder="輸入電子信箱" required>
        <input class="dialog__input" type="password" name="password" placeholder="輸入密碼" required>
        <button type="submit" class="dialog__submit">註冊新帳戶</button>
        <p class="dialog__message" id="signup-message"></p>
        <p class="dialog__switch">已經有帳戶了？<span class="dialog__link" id="to-signin">點此登入</span></p>
      </form>
    </div>
  </div>
`);

/* ---------- DOM 元素 ----------
   authLink 是兩頁 HTML 裡本來就有的「登入/註冊」連結（id="auth-link"）
   其餘都在上面剛注入的彈窗裡                                       */
const authLink      = document.querySelector("#auth-link");
const overlayEl     = document.querySelector("#auth-overlay");
const closeBtn      = document.querySelector("#auth-close");
const signinForm    = document.querySelector("#signin-form");
const signupForm    = document.querySelector("#signup-form");
const signinMessage = document.querySelector("#signin-message");
const signupMessage = document.querySelector("#signup-message");
const toSignup      = document.querySelector("#to-signup");
const toSignin      = document.querySelector("#to-signin");

/* ---------- 全域狀態 ---------- */
let isSignedIn = false;   // 由 checkSigninStatus() 決定，authLink 點擊行為依它分流


/* ============================================================
   Part 4-3：登入狀態檢查（頁面載入立刻執行）
   ============================================================ */

/**
 * 問後端「我是誰」，依回答決定右上角顯示「登入/註冊」還是「登出系統」。
 * 規格：GET /api/user/auth，token 放 Authorization: Bearer 標頭；
 * 沒登入時後端回 {"data": null}，是正常回應不是錯誤。
 */
async function checkSigninStatus() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return;   // 連 token 都沒有，必定未登入，不用浪費一次 API

  try {
    const response = await fetch("/api/user/auth", {
      headers: { "Authorization": `Bearer ${token}` },
    });
    const result = await response.json();

    if (result.data) {
      isSignedIn = true;
      authLink.textContent = "登出系統";
    } else {
      // token 過期或無效：清掉，免得每頁都白問一次
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch (error) {
    console.error("登入狀態檢查失敗：", error);  // 網路問題時保持未登入外觀即可
  }
}

checkSigninStatus();


/* ============================================================
   彈窗開關與表單切換
   ============================================================ */

function openDialog() {
  // 每次打開都回到預設狀態：顯示登入表單、清空上次的訊息
  signinForm.hidden = false;
  signupForm.hidden = true;
  clearMessages();
  overlayEl.hidden = false;
}

function closeDialog() {
  overlayEl.hidden = true;
}

function clearMessages() {
  signinMessage.textContent = "";
  signupMessage.textContent = "";
}

/* Part 4-6：右上角連結——已登入按下去是登出，未登入按下去開彈窗 */
authLink.addEventListener("click", (event) => {
  event.preventDefault();   // <a href="#"> 預設會把網址加上 # 並捲到頁首，擋掉
  if (isSignedIn) {
    localStorage.removeItem(TOKEN_KEY);  // 登出＝丟掉 token，後端不用知道
    location.reload();                   // 重新整理，讓狀態檢查重跑
  } else {
    openDialog();
  }
});

closeBtn.addEventListener("click", closeDialog);

/* 點半透明黑底（彈窗以外的區域）也能關閉；
   點彈窗本身會冒泡到 overlay，用 event.target 判斷起點是不是 overlay 自己 */
overlayEl.addEventListener("click", (event) => {
  if (event.target === overlayEl) closeDialog();
});

/* Part 4-2：兩張表單互相切換，切換時清掉舊訊息 */
toSignup.addEventListener("click", () => {
  signinForm.hidden = true;
  signupForm.hidden = false;
  clearMessages();
});

toSignin.addEventListener("click", () => {
  signupForm.hidden = true;
  signinForm.hidden = false;
  clearMessages();
});


/* ============================================================
   Part 4-4：註冊流程
   ============================================================ */
signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();   // 🔴 擋掉表單預設送出（會整頁重新載入）

  // FormData 依 input 的 name 屬性取值，欄位增減不用改 JS
  const formData = new FormData(signupForm);

  try {
    const response = await fetch("/api/user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: formData.get("name"),
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    const result = await response.json();

    if (result.ok) {
      showMessage(signupMessage, "註冊成功，請登入系統", true);
      signupForm.reset();
    } else {
      // 後端把原因寫在 message（重複 Email、欄位空白…），直接顯示
      showMessage(signupMessage, result.message, false);
    }
  } catch (error) {
    console.error("註冊失敗：", error);
    showMessage(signupMessage, "連線失敗，請稍後再試", false);
  }
});


/* ============================================================
   Part 4-5：登入流程
   ============================================================ */
signinForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(signinForm);

  try {
    const response = await fetch("/api/user/auth", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: formData.get("email"),
        password: formData.get("password"),
      }),
    });
    const result = await response.json();

    if (result.token) {
      // 規格：token 存 LocalStorage，之後每次呼叫需授權的 API 都帶它
      localStorage.setItem(TOKEN_KEY, result.token);
      location.reload();   // 規格：登入成功後重新整理，取得最新登入狀態
    } else {
      showMessage(signinMessage, result.message, false);
    }
  } catch (error) {
    console.error("登入失敗：", error);
    showMessage(signinMessage, "連線失敗，請稍後再試", false);
  }
});


/** 在視窗底部顯示訊息；isSuccess 決定綠字或紅字（樣式在 style.css）。 */
function showMessage(element, text, isSuccess) {
  element.textContent = text;
  element.classList.toggle("dialog__message--success", isSuccess);
}
