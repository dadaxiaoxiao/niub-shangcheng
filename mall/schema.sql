-- Niub Shangcheng database schema (MySQL 8.0+).
--
-- This file is the single source of truth for the DDL.
--
-- Manual use on a fresh machine: execute the whole file in any MySQL client
-- (mysql CLI, DBX, etc). The database name below is the default; change it if
-- you configure a different MALL_DB_URL.
--
-- The mall service also applies this file on startup (or via
-- `uv run python -m mall.init_db`). In that path the CREATE DATABASE and USE
-- statements are skipped, so the database configured in MALL_DB_URL is used.

CREATE DATABASE IF NOT EXISTS `niub_shop`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE `niub_shop`;

CREATE TABLE IF NOT EXISTS conversations (
  id         CHAR(36)     NOT NULL,
  title      VARCHAR(200) NOT NULL DEFAULT '',
  created_at DATETIME(3)  NOT NULL,
  updated_at DATETIME(3)  NOT NULL,
  PRIMARY KEY (id),
  KEY idx_conversations_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS messages (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  conversation_id CHAR(36)        NOT NULL,
  role            VARCHAR(16)     NOT NULL CHECK (role IN ('user', 'assistant')),
  content         MEDIUMTEXT      NOT NULL,
  status          VARCHAR(16)     NOT NULL DEFAULT 'complete' CHECK (status IN ('complete', 'interrupted')),
  created_at      DATETIME(3)     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_messages_conversation (conversation_id, id),
  CONSTRAINT fk_messages_conversation
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;