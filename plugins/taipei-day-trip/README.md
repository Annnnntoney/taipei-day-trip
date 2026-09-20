# 台北一日遊 Codex Plugin

讓你在 Codex 裡直接搜尋台北市景點並預定一日導覽行程。

## 使用前設定

1. 到 [台北一日遊會員中心](http://43.213.133.188:8000/member) 登入並點「產生 / 更新金鑰」。
2. 打開本資料夾的 `mcp.json`，把 `Authorization` 的值換成：
   `Bearer 你的金鑰`（保留 `Bearer ` 前綴與空格）。

## 安裝到 Codex 專案

1. 建立（或打開）一個測試專案資料夾，把整個 `taipei-day-trip` 資料夾複製進去，
   例如放在 `plugins/taipei-day-trip`。
2. 在專案根目錄建立 `.agents/plugins/marketplace.json`：

```json
{
  "name": "repo-marketplace",
  "interface": { "displayName": "Repo Plugins" },
  "plugins": [
    {
      "name": "taipei-day-trip",
      "source": { "source": "local", "path": "./plugins/taipei-day-trip" },
      "policy": { "installation": "AVAILABLE" }
    }
  ]
}
```

（`source.path` 是相對於 marketplace 檔案所在根目錄、以 `./` 開頭的路徑，依實際擺放位置調整。）

3. 在 Codex 裡執行 `/plugins`，找到 台北一日遊（taipei-day-trip）→ Install plugin。
4. 重開一個新的 Codex 對話（安裝後要下個 session 才生效）。

## 使用方式

在 Codex 輸入：

```
@taipei-day-trip 預定台北市一日遊行程
```

依照提示輸入關鍵字 → 選景點編號、日期、時段 → 取得預定頁面連結完成付款。
