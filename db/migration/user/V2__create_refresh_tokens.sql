CREATE TABLE refresh_tokens (
    id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    token_hash VARCHAR(500) NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    revoked_at DATETIME(6) NULL,

    PRIMARY KEY (id),

    CONSTRAINT fk_refresh_tokens_users
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    UNIQUE KEY uk_refresh_tokens_token_hash (token_hash),
    INDEX idx_refresh_tokens_user_id (user_id),
    INDEX idx_refresh_tokens_expires_at (expires_at)
) ENGINE=InnoDB;
