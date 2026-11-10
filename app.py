from flask import Flask, render_template, request, jsonify
from flask_mysqldb import MySQL

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'shkurte@bytyqi1'
app.config['MYSQL_DB'] = 'complaint_db'

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('full_name') or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'message': 'Të gjitha fushat janë të detyrueshme!'}), 400
    
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, %s)",
                   (data['full_name'], data['email'], data['password'], data.get('role', 'client')))
    mysql.connection.commit()
    cursor.close()
    return jsonify({'success': True, 'message': 'Përdoruesi u regjistrua me sukses!'}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'message': 'Email dhe fjalëkalimi janë të detyrueshëm!'}), 400
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, full_name, role FROM users WHERE email = %s AND password = %s",
                   (data['email'], data['password']))
    user = cursor.fetchone()
    cursor.close()
    
    if user:
        return jsonify({'success': True, 'message': 'Kyçja u realizua me sukses!', 'user': {'id': user[0], 'name': user[1], 'role': user[2]}}), 200
    return jsonify({'success': False, 'message': 'Kredencialet janë të gabuara!'}), 401

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, title, description, status, priority FROM complaints")
    rows = cursor.fetchall()
    cursor.close()
    
    complaints = [{'id': r[0], 'title': r[1], 'description': r[2], 'status': r[3], 'priority': r[4]} for r in rows]
    return jsonify({'success': True, 'data': complaints}), 200

@app.route('/api/complaints', methods=['POST'])
def create_complaint():
    data = request.get_json()
    if not data or not data.get('title') or not data.get('description'):
        return jsonify({'success': False, 'message': 'Titulli dhe përshkrimi janë të detyrueshëm!'}), 400
    
    cursor = mysql.connection.cursor()
    
    cursor.execute("SELECT id FROM users LIMIT 1")
    user = cursor.fetchone()
    
    if user:
        user_id = user[0]
    else:
        cursor.execute("INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, %s)",
                       ('Klient Vizitor', 'vizitor@example.com', '123456', 'client'))
        mysql.connection.commit()
        user_id = cursor.lastrowid

    kategoria_zgjedhur = data.get('priority', 'Teknike')
    pershkrimi_plote = f"[{kategoria_zgjedhur}] " + data['description']

    cursor.execute("INSERT INTO complaints (user_id, category_id, title, description, priority) VALUES (%s, %s, %s, %s, %s)",
                   (user_id, data.get('category_id', 1), data['title'], pershkrimi_plote, 'Mesatare'))
    mysql.connection.commit()
    complaint_id = cursor.lastrowid
    cursor.close()
    
    return jsonify({'success': True, 'message': 'Ankesa u krijua me sukses.', 'complaint_id': complaint_id}), 201

if __name__ == '__main__':
    app.run(debug=True, port=5000)