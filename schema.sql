CREATE DATABASE IF NOT EXISTS complaint_db;
USE complaint_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('client', 'admin') DEFAULT 'client',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category_id INT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar') DEFAULT 'Në pritje',
    priority ENUM('E ulët', 'Mesatare', 'E lartë') DEFAULT 'Mesatare',
    category_name VARCHAR(100) DEFAULT 'Tjetër',
    complaint_type VARCHAR(100) DEFAULT 'Online',
    admin_response TEXT NULL,
    assigned_admin_id INT NULL,
    due_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    FOREIGN KEY (assigned_admin_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS complaint_status_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    status ENUM('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar') NOT NULL,
    changed_by INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS complaint_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    user_id INT NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS complaint_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    uploaded_by INT NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    size INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
);

INSERT INTO categories (name, description) VALUES
('Probleme Teknike', 'Ankesa lidhur me problemet teknike dhe sistemin'),
('Faturim & Pagesa', 'Çështje që lidhen me pagesat dhe faturat'),
('Cilësia e Shërbimit', 'Vërejtje mbi cilësinë e shërbimit të klientit'),
('Stafi & Komunikimi', 'Probleme me komunikimin dhe sjelljen e stafit'),
('Vonesa / Afatet', 'Ankesa për vonesa dhe mosrespektim të afateve'),
('Llogaria & Qasja', 'Probleme me hyrjen dhe menaxhimin e llogarisë'),
('Siguria & Privatësia', 'Ankesa për sigurinë dhe privatësinë e të dhënave'),
('Kontrata & Kushtet', 'Pyetje dhe ankesa mbi kontratat dhe kushtet'),
('Tjetër', 'Kategori të tjera')
ON DUPLICATE KEY UPDATE name=name;

-- Për databazën që është krijuar më parë
ALTER TABLE complaints
MODIFY COLUMN category_id INT NULL,
MODIFY COLUMN status ENUM('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar') DEFAULT 'Në pritje',
ADD COLUMN IF NOT EXISTS category_name VARCHAR(100) DEFAULT 'Tjetër',
ADD COLUMN IF NOT EXISTS complaint_type VARCHAR(100) DEFAULT 'Online',
ADD COLUMN IF NOT EXISTS admin_response TEXT NULL,
ADD COLUMN IF NOT EXISTS created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS assigned_admin_id INT NULL,
ADD COLUMN IF NOT EXISTS due_at DATETIME NULL;