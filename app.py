from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import mysql.connector
import bcrypt
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape

def load_environment_file(filename='.env'):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.isfile(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

load_environment_file()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError('Set SECRET_KEY in the environment or .env file.')
CORS(app)

VALID_STATUSES = ('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar')
VALID_PRIORITIES = ('E ulët', 'Mesatare', 'E lartë')

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE', 'complaint_db')
    )

def send_complaint_email(complaint_id, client_name, client_email, category_name,
                         complaint_type, priority, description):
    sender = os.getenv('GMAIL_ADDRESS', '').strip()
    app_password = os.getenv('GMAIL_APP_PASSWORD', '').strip()
    recipient = os.getenv('ADMIN_EMAIL', sender).strip()

    if not sender or not app_password or not recipient:
        app.logger.warning(
            'Njoftimi me email nuk u dërgua: konfiguro GMAIL_ADDRESS, '
            'GMAIL_APP_PASSWORD dhe ADMIN_EMAIL.'
        )
        return False, 'Email-i nuk është konfiguruar.'

    urgent_label = 'PO' if priority == 'E lartë' else 'JO'
    created_at = datetime.now().strftime('%d/%m/%Y %H:%M')
    subject = (
        f"[URGJENTE] Ankesa #{complaint_id} - {category_name}"
        if priority == 'E lartë'
        else f"Ankesa #{complaint_id} - {category_name}"
    )

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = recipient
    if client_email:
        message['Reply-To'] = client_email

    plain_text = (
        f"U pranua një ankesë e re.\n\n"
        f"ID: #{complaint_id}\n"
        f"Ankuesi: {client_name}\n"
        f"Email i ankuesit: {client_email or 'Nuk është dhënë'}\n"
        f"Kategoria: {category_name}\n"
        f"Forma: {complaint_type}\n"
        f"Urgjente: {urgent_label}\n"
        f"Prioriteti: {priority}\n"
        f"Ora: {created_at}\n"
        f"Statusi: Në pritje\n\n"
        f"Mesazhi:\n{description}"
    )

    html_body = f"""
    <h2>Ankesë e re #{escape(str(complaint_id))}</h2>
    <table cellpadding="6">
      <tr><td><strong>Ankuesi</strong></td><td>{escape(client_name)}</td></tr>
      <tr><td><strong>Email</strong></td><td>{escape(client_email or 'Nuk është dhënë')}</td></tr>
      <tr><td><strong>Kategoria</strong></td><td>{escape(category_name)}</td></tr>
      <tr><td><strong>Forma</strong></td><td>{escape(complaint_type)}</td></tr>
      <tr><td><strong>Prioriteti</strong></td><td>{escape(priority)}</td></tr>
      <tr><td><strong>Urgjente</strong></td><td>{urgent_label}</td></tr>
      <tr><td><strong>Ora</strong></td><td>{escape(created_at)}</td></tr>
      <tr><td><strong>Statusi</strong></td><td>Në pritje</td></tr>
    </table>
    <h3>Mesazhi</h3>
    <p>{escape(description).replace(chr(10), '<br>')}</p>
    """

    message.set_content(plain_text)
    message.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP(os.getenv('SMTP_HOST', 'smtp.gmail.com'),
                          int(os.getenv('SMTP_PORT', '587'))) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(sender, app_password)
            smtp.send_message(message)
        return True, 'Email-i u dërgua.'
    except (smtplib.SMTPException, OSError, ValueError) as error:
        app.logger.error('Gabim në dërgimin e email-it: %s', error)
        return False, 'Email-i nuk u dërgua.'

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').encode('utf-8')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'index'))
        else:
            error = "Email-i ose fjalëkalimi është i pasaktë."

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').encode('utf-8')

        if len(full_name) < 2:
            error = "Emri i plotë duhet të ketë të paktën 2 karaktere."
        elif '@' not in email or '.' not in email:
            error = "Email-i i dhënë nuk është i vlefshëm."
        elif len(password) < 8:
            error = "Fjalëkalimi duhet të ketë të paktën 8 karaktere."

        if error:
            return render_template('register.html', error=error)

        hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            error = "Ky email ekziston tashmë!"
        else:
            cursor.execute(
                "INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, 'client')",
                (full_name, email, hashed)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('login'))
        cursor.close()
        conn.close()

    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query_base = """
        SELECT c.id, c.title, c.description, c.status, c.priority,
               COALESCE(cat.name, 'Tjetër') AS category_name,
               COALESCE(c.complaint_type, 'Online') AS complaint_type,
               COALESCE(c.admin_response, '') AS admin_response,
               DATE_FORMAT(c.created_at, '%d/%m/%Y') AS created_date,
               DATE_FORMAT(c.created_at, '%H:%i') AS created_time,
               u.full_name, u.id AS user_id
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN categories cat ON c.category_id = cat.id
    """

    if session.get('role') == 'admin':
        cursor.execute(query_base + " ORDER BY c.id DESC")
    else:
        cursor.execute(
            query_base + " WHERE c.user_id = %s ORDER BY c.id DESC",
            (session['user_id'],)
        )

    complaints = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(complaints)

@app.route('/api/complaints', methods=['POST'])
def create_complaint():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    category_name = (data.get('category') or 'Tjetër').strip()
    complaint_type = (data.get('complaint_type') or 'Online').strip()
    priority = (data.get('priority') or 'Mesatare').strip()
    description = (data.get('description') or '').strip()

    if len(description) < 10:
        return jsonify({'error': 'Përshkrimi duhet të ketë të paktën 10 karaktere.'}), 400
    if priority not in VALID_PRIORITIES:
        return jsonify({'error': 'Niveli i urgjencës nuk është i vlefshëm.'}), 400

    title = f"[{category_name}] Ankesë {complaint_type}"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(%s) LIMIT 1", (category_name,))
    cat_row = cursor.fetchone()
    if not cat_row:
        cursor.execute("SELECT id FROM categories ORDER BY id ASC LIMIT 1")
        cat_row = cursor.fetchone()

    category_id = cat_row['id'] if cat_row else 1

    cursor.execute("""
        INSERT INTO complaints (user_id, category_id, complaint_type, title, description, status, priority)
        VALUES (%s, %s, %s, %s, %s, 'Në pritje', %s)
    """, (session['user_id'], category_id, complaint_type, title, description, priority))
    complaint_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO complaint_status_history (complaint_id, status, changed_by)
        VALUES (%s, 'Në pritje', %s)
    """, (complaint_id, session['user_id']))
    conn.commit()

    cursor.execute("SELECT full_name, email FROM users WHERE id = %s", (session['user_id'],))
    client = cursor.fetchone()
    client_name = client['full_name'] if client else session.get('full_name', 'Klient')
    client_email = client['email'] if client else ''

    cursor.close()
    conn.close()
    email_sent, email_message = send_complaint_email(
        complaint_id,
        client_name,
        client_email,
        category_name,
        complaint_type,
        priority,
        description
    )

    return jsonify({
        'success': True,
        'complaint_id': complaint_id,
        'email_sent': email_sent,
        'email_message': email_message
    }), 201

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    selected_user_id = request.args.get('user_id', type=int)
    selected_status = request.args.get('status', '').strip()
    selected_category = request.args.get('category', '').strip()
    selected_priority = request.args.get('priority', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total,
               SUM(status = 'Në pritje') AS pending,
               SUM(status = 'Në shqyrtim') AS reviewing,
               SUM(status = 'Zgjidhur') AS resolved,
               SUM(status = 'Refuzuar') AS rejected
        FROM complaints
    """)
    stats = cursor.fetchone()

    cursor.execute("""
        SELECT DISTINCT u.id, u.full_name, COUNT(c.id) AS total_complaints
        FROM users u
        JOIN complaints c ON c.user_id = u.id
        GROUP BY u.id, u.full_name
        ORDER BY u.full_name ASC
    """)
    clients = cursor.fetchall()

    cursor.execute("SELECT name FROM categories ORDER BY name ASC")
    categories = cursor.fetchall()

    base_sql = """
        SELECT c.id, c.title, c.description, c.status, c.priority,
               COALESCE(cat.name, 'Tjetër') AS category_name,
               COALESCE(c.complaint_type, 'Online') AS complaint_type,
               COALESCE(c.admin_response, '') AS admin_response,
               DATE_FORMAT(c.created_at, '%d/%m/%Y') AS created_date,
               DATE_FORMAT(c.created_at, '%H:%i') AS created_time,
               u.full_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN categories cat ON c.category_id = cat.id
    """

    conditions = []
    params = []
    if selected_user_id:
        conditions.append("c.user_id = %s")
        params.append(selected_user_id)
    if selected_status in VALID_STATUSES:
        conditions.append("c.status = %s")
        params.append(selected_status)
    if selected_category:
        conditions.append("cat.name = %s")
        params.append(selected_category)
    if selected_priority in VALID_PRIORITIES:
        conditions.append("c.priority = %s")
        params.append(selected_priority)

    if conditions:
        cursor.execute(base_sql + " WHERE " + " AND ".join(conditions) + " ORDER BY c.id DESC", tuple(params))
    else:
        cursor.execute(base_sql + " ORDER BY c.id DESC")

    complaints = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'admin.html',
        complaints=complaints,
        clients=clients,
        selected_user_id=selected_user_id,
        selected_status=selected_status,
        selected_category=selected_category,
        selected_priority=selected_priority,
        stats=stats,
        statuses=VALID_STATUSES,
        priorities=VALID_PRIORITIES,
        categories=categories
    )

@app.route('/api/complaints/<int:complaint_id>/comment', methods=['POST'])
def save_complaint_comment(complaint_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET admin_response = %s WHERE id = %s", (comment, complaint_id))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'comment': comment})

@app.route('/resolve/<int:id>', methods=['POST'])
def resolve_complaint(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT status FROM complaints WHERE id = %s", (id,))
    complaint = cursor.fetchone()
    if complaint and complaint['status'] != 'Zgjidhur':
        cursor.execute("UPDATE complaints SET status = 'Zgjidhur' WHERE id = %s", (id,))
        cursor.execute("""
            INSERT INTO complaint_status_history (complaint_id, status, changed_by)
            VALUES (%s, 'Zgjidhur', %s)
        """, (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/api/complaints/<int:complaint_id>/history', methods=['GET'])
def get_complaint_history(complaint_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id FROM complaints WHERE id = %s", (complaint_id,))
    complaint = cursor.fetchone()
    if not complaint:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Ankesa nuk u gjet.'}), 404
    if session.get('role') != 'admin' and complaint['user_id'] != session['user_id']:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Forbidden'}), 403

    cursor.execute("""
        SELECT h.status,
               DATE_FORMAT(h.created_at, '%d/%m/%Y %H:%i') AS created_at,
               COALESCE(u.full_name, 'Sistemi') AS changed_by_name
        FROM complaint_status_history h
        LEFT JOIN users u ON h.changed_by = u.id
        WHERE h.complaint_id = %s
        ORDER BY h.created_at ASC, h.id ASC
    """, (complaint_id,))
    history = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(history)

@app.route('/api/complaints/<int:complaint_id>/status', methods=['POST'])
def update_complaint_status(complaint_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    status = (data.get('status') or '').strip()
    if status not in VALID_STATUSES:
        return jsonify({'error': 'Statusi nuk është i vlefshëm.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT status FROM complaints WHERE id = %s", (complaint_id,))
    complaint = cursor.fetchone()
    if not complaint:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Ankesa nuk u gjet.'}), 404

    if complaint['status'] != status:
        cursor.execute("UPDATE complaints SET status = %s WHERE id = %s", (status, complaint_id))
        cursor.execute("""
            INSERT INTO complaint_status_history (complaint_id, status, changed_by)
            VALUES (%s, %s, %s)
        """, (complaint_id, status, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'status': status})

@app.route('/delete/<int:id>', methods=['POST'])
def delete_complaint(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
