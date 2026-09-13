-- Taipei Day Trip — 資料表結構
-- 用法：mysql -u tdt -p taipei_day_trip < schema.sql
-- ⚠️ 這是「整個重置」腳本：重跑會清空所有資料（含會員與預定行程），只想加單一張表時，單獨執行該表的 CREATE 區塊即可

-- DROP 集中在最上面，依「子表 → 父表」順序：
-- bookings/order_payments/orders 的外鍵指向 members 與 attractions，若先砍父表會被外鍵擋下（errno 3730）
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS attraction_images;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS attractions;

CREATE TABLE attractions (
  id          INT           NOT NULL PRIMARY KEY,   -- 沿用 JSON 的 _id，不自動編號
  name        VARCHAR(100)  NOT NULL,               -- 實測最長 18
  category    VARCHAR(50)   NOT NULL,               -- 實測最長 4
  description TEXT          NOT NULL,               -- 實測最長 1691，放列外
  address     VARCHAR(255)  NOT NULL,               -- 實測最長 30
  transport   TEXT,                                 -- 實測最長 487
  mrt         VARCHAR(50)   NULL,                   -- 有一筆是 null
  lat         DECIMAL(9, 6) NOT NULL,
  lng         DECIMAL(9, 6) NOT NULL,
  INDEX idx_category (category),
  INDEX idx_mrt (mrt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 會員（Part 4）
CREATE TABLE members (
  id         INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(100)  NOT NULL,
  email      VARCHAR(255)  NOT NULL,
  password   VARCHAR(255)  NOT NULL,              -- 存 bcrypt 雜湊，不存明文
  created_at TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_email (email)                     -- 資料庫層擋重複註冊，不能只靠程式檢查
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE attraction_images (
  id            INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
  attraction_id INT          NOT NULL,
  url           VARCHAR(255) NOT NULL,
  INDEX idx_attraction (attraction_id),
  CONSTRAINT fk_images_attraction
    FOREIGN KEY (attraction_id) REFERENCES attractions(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 預定行程（Part 5）
-- 每位會員同時只能有一筆預定行程：靠 UNIQUE(member_id) 保證，建立新預定時直接 ON DUPLICATE KEY UPDATE 覆蓋
CREATE TABLE bookings (
  id            INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
  member_id     INT           NOT NULL,
  attraction_id INT           NOT NULL,
  date          DATE          NOT NULL,
  time          VARCHAR(10)   NOT NULL,              -- "morning" 或 "afternoon"
  price         INT           NOT NULL,               -- 2000 或 2500
  UNIQUE KEY uq_member (member_id),
  CONSTRAINT fk_booking_member
    FOREIGN KEY (member_id) REFERENCES members(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_booking_attraction
    FOREIGN KEY (attraction_id) REFERENCES attractions(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 訂單（Part 6）
-- number 是時間戳記＋亂數組成的字串（app.py 的 generate_order_number），不是自動編號，
-- 因為它要直接回給前端當「訂單編號」顯示，用資料庫的 AUTO_INCREMENT 會暴露總單量
CREATE TABLE orders (
  number        VARCHAR(20)   NOT NULL PRIMARY KEY,
  member_id     INT           NOT NULL,
  attraction_id INT           NOT NULL,
  date          DATE          NOT NULL,
  time          VARCHAR(10)   NOT NULL,              -- "morning" 或 "afternoon"
  price         INT           NOT NULL,               -- 2000 或 2500
  contact_name  VARCHAR(100)  NOT NULL,
  contact_email VARCHAR(255)  NOT NULL,
  contact_phone VARCHAR(20)   NOT NULL,
  status        TINYINT       NOT NULL DEFAULT 0,      -- 0 = UNPAID，1 = PAID
  created_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_member (member_id),
  CONSTRAINT fk_order_member
    FOREIGN KEY (member_id) REFERENCES members(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_order_attraction
    FOREIGN KEY (attraction_id) REFERENCES attractions(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 每次呼叫 TapPay Pay By Prime 的結果都存一筆，一張訂單可能對到多筆
-- （例如失敗後允許使用者重新輸入信用卡再試一次，之後如果要做這個功能，紀錄不會互相覆蓋）
CREATE TABLE order_payments (
  id                  INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
  order_number        VARCHAR(20)   NOT NULL,
  tappay_status       INT           NOT NULL,          -- TapPay 回傳的 status，0 為成功
  tappay_message      VARCHAR(255)  NOT NULL,
  rec_trade_id        VARCHAR(100)  NULL,
  bank_transaction_id VARCHAR(100)  NULL,
  created_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_order (order_number),
  CONSTRAINT fk_payment_order
    FOREIGN KEY (order_number) REFERENCES orders(number)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
