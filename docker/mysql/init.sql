-- Initialize InsightMesh databases and users

-- Create databases
CREATE DATABASE IF NOT EXISTS insightmesh_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS insightmesh_security CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS insightmesh_task CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS insightmesh_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create users and grant permissions
CREATE USER IF NOT EXISTS 'insightmesh_data'@'%' IDENTIFIED BY 'insightmesh_data_password';
GRANT ALL PRIVILEGES ON insightmesh_data.* TO 'insightmesh_data'@'%';

CREATE USER IF NOT EXISTS 'insightmesh_security'@'%' IDENTIFIED BY 'insightmesh_security_password';
GRANT ALL PRIVILEGES ON insightmesh_security.* TO 'insightmesh_security'@'%';

CREATE USER IF NOT EXISTS 'insightmesh_tasks'@'%' IDENTIFIED BY 'insightmesh_tasks_password';
GRANT ALL PRIVILEGES ON insightmesh_task.* TO 'insightmesh_tasks'@'%';

CREATE USER IF NOT EXISTS 'insightmesh_system'@'%' IDENTIFIED BY 'insightmesh_system_password';
GRANT ALL PRIVILEGES ON insightmesh_system.* TO 'insightmesh_system'@'%';

FLUSH PRIVILEGES;

-- Create agent_usage table in system database
USE insightmesh_system;

CREATE TABLE IF NOT EXISTS agent_usage (
    id INT PRIMARY KEY AUTO_INCREMENT,
    agent_name VARCHAR(100) NOT NULL UNIQUE,

    -- Metrics
    total_invocations INT NOT NULL DEFAULT 0,
    successful_invocations INT NOT NULL DEFAULT 0,
    failed_invocations INT NOT NULL DEFAULT 0,

    -- Timestamps
    first_invocation DATETIME NULL,
    last_invocation DATETIME NULL,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX ix_agent_usage_agent_name (agent_name),
    INDEX ix_agent_usage_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
