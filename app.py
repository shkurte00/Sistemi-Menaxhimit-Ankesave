from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import mysql.connector
import time 

app = Flask(__name__)
CORS(app)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'shkurte@bytyqi1',
    'database': 'complaint_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT c.id, u.full_name AS client_name, cat.name AS category, c.title, c.description, c.status 
            FROM complaints c
            JOIN users u ON c.user_id = u.id
            JOIN categories cat ON c.category_id = cat.id
            ORDER BY c.id DESC
        """
        cursor.execute(query)
        complaints = cursor.fetchall()
    except Exception as e:
        cursor.execute("SELECT id, 'Klient' AS client_name, 'Teknike' AS category, title, description, status FROM complaints ORDER BY id DESC")
        complaints = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify(complaints), 200

@app.route('/api/complaints', methods=['POST'])
def create_complaint():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    client_name = data.get('client_name') or data.get('clientName') or 'Klient Anonim'
    category_name = data.get('category') or 'Teknike'
    description = data.get('description')

    if not description:
        return jsonify({'error': 'Missing description'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users LIMIT 1")
    user_row = cursor.fetchone()
    
    if user_row:
        user_id = user_row[0]
        cursor.execute("UPDATE users SET full_name = %s WHERE id = %s", (client_name, user_id))
    else:
        cursor.execute("INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, %s)", 
                       (client_name, f"klient_{int(time.time())}@test.com", "123456", "client"))
        user_id = cursor.lastrowid

    cursor.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
    cat_row = cursor.fetchone()
    
    if cat_row:
        category_id = cat_row[0]
    else:
        cursor.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (category_name, 'Kategori'))
        category_id = cursor.lastrowid

    title = description[:30] + '...' if len(description) > 30 else description

    query = "INSERT INTO complaints (user_id, category_id, title, description, status) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(query, (user_id, category_id, title, description, 'Në pritje'))
    conn.commit()
    
    cursor.close()
    conn.close()

    return jsonify({'message': 'Complaint created successfully'}), 201

if __name__ == '__main__':
    app.run(debug=True)