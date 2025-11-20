\c emaildb;

CREATE TABLE IF NOT EXISTS emails (
    id VARCHAR(16) PRIMARY KEY,
    subject_title TEXT,
    from_addr TEXT,
    to_addr TEXT,
    received_date TIMESTAMP
);
