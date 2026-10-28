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
    category_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar') DEFAULT 'Në pritje',
    priority ENUM('E ulët', 'Mesatare', 'E lartë') DEFAULT 'Mesatare',
    admin_response TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
);

INSERT INTO categories (name, description) VALUES
('Teknike', 'Ankesa lidhur me problemet teknike dhe sistemin'),
('Financiare', 'Çështje që lidhen me pagesat dhe faturat'),
('Shërbim', 'Vërejtje mbi cilësinë e shërbimit të klientit')
ON DUPLICATE KEY UPDATE name=name;