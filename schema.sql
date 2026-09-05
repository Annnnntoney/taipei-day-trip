-- Taipei Day Trip — 資料表結構
-- 用法：mysql -u tdt -p taipei_day_trip < schema.sql

DROP TABLE IF EXISTS attraction_images;
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
-- 注意：整份 schema.sql 重跑會清空景點資料；只想加這張表時，單獨執行這個區塊即可
DROP TABLE IF EXISTS members;
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
-- 注意：整份 schema.sql 重跑會清空景點資料；只想加這張表時，單獨執行這個區塊即可
-- 每位會員同時只能有一筆預定行程：靠 UNIQUE(member_id) 保證，建立新預定時直接 ON DUPLICATE KEY UPDATE 覆蓋
DROP TABLE IF EXISTS bookings;
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
