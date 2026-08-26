CREATE TABLE IF NOT EXISTS inquiry (
    id BIGINT NOT NULL AUTO_INCREMENT,
    member_id BIGINT NULL,
    name VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    type VARCHAR(30) NOT NULL,
    title VARCHAR(80) NOT NULL,
    message VARCHAR(1000) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    answered_at TIMESTAMP NULL,
    PRIMARY KEY (id),
    INDEX idx_inquiry_status_created_at (status, created_at),
    INDEX idx_inquiry_email_created_at (email, created_at)
);
