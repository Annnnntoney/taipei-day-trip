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

CREATE TABLE attraction_images (
  id            INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
  attraction_id INT          NOT NULL,
  url           VARCHAR(255) NOT NULL,              
  INDEX idx_attraction (attraction_id),
  CONSTRAINT fk_images_attraction
    FOREIGN KEY (attraction_id) REFERENCES attractions(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
