-- V7.2 数据库迁移脚本：添加 UUID 字段
-- 用途：为现有数据库添加异步关联所需的 UUID 字段
-- 执行方式：sqlite3 database.db < migrations/add_uuid_fields_v7.2.sql
-- 安全性：可重复执行（使用 IF NOT EXISTS）

-- ============================================================
-- 手术一：chat_sessions 表添加 session_uuid
-- ============================================================
-- 作用：前端会话 ID（URL 参数），避免暴露自增 ID
ALTER TABLE chat_sessions ADD COLUMN session_uuid TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uix_chat_sessions_session_uuid ON chat_sessions(session_uuid);

-- 为现有会话生成 UUID（如果字段为空）
UPDATE chat_sessions
SET session_uuid = lower(hex(randomblob(16)))
WHERE session_uuid IS NULL;

-- ============================================================
-- 手术二：chat_messages 表添加 msg_uuid
-- ============================================================
-- 作用：LangChain Message UUID，用于 Profiler 异步关联
ALTER TABLE chat_messages ADD COLUMN msg_uuid TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uix_chat_messages_msg_uuid ON chat_messages(msg_uuid);

-- 为现有消息生成 UUID（如果字段为空）
UPDATE chat_messages
SET msg_uuid = lower(hex(randomblob(16)))
WHERE msg_uuid IS NULL;

-- ============================================================
-- 手术三：raw_observations 表修改（如果使用旧版本）
-- ============================================================
-- 注意：如果已有 source_msg_uuid 字段，跳过此步骤
-- 检查方式：PRAGMA table_info(raw_observations);

-- 如果只有 source_message_id，需要迁移：
-- 1. 添加新字段
-- ALTER TABLE raw_observations ADD COLUMN source_msg_uuid TEXT;
-- CREATE INDEX IF NOT EXISTS idx_raw_obs_source_uuid ON raw_observations(source_msg_uuid);
--
-- 2. 迁移数据（可选，需要关联查询）
-- UPDATE raw_observations
-- SET source_msg_uuid = (
--     SELECT msg_uuid FROM chat_messages
--     WHERE chat_messages.id = raw_observations.source_message_id
-- )
-- WHERE source_message_id IS NOT NULL;

-- ============================================================
-- 手术四：profile_sections 表添加 tags
-- ============================================================
-- 作用：技能/角色标签列，用于快速查询和筛选
ALTER TABLE profile_sections ADD COLUMN tags TEXT;
-- 注意：SQLite 不支持 JSON 类型，使用 TEXT 存储 JSON 字符串
-- 示例值：'["Python", "Backend", "FastAPI"]'

-- ============================================================
-- 验证迁移结果
-- ============================================================
-- 查看表结构：
-- PRAGMA table_info(chat_sessions);
-- PRAGMA table_info(chat_messages);
-- PRAGMA table_info(raw_observations);
-- PRAGMA table_info(profile_sections);

-- 查看索引：
-- PRAGMA index_list(chat_sessions);
-- PRAGMA index_list(chat_messages);
-- PRAGMA index_list(raw_observations);

-- 验证数据完整性：
-- SELECT COUNT(*) as sessions_without_uuid FROM chat_sessions WHERE session_uuid IS NULL;
-- SELECT COUNT(*) as messages_without_uuid FROM chat_messages WHERE msg_uuid IS NULL;
