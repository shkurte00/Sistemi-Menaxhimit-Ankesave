from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import bcrypt
import os
import smtplib
import secrets
from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
from werkzeug.utils import secure_filename
from flask import send_from_directory

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
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

VALID_STATUSES = ('Në pritje', 'Në shqyrtim', 'Zgjidhur', 'Refuzuar')
VALID_PRIORITIES = ('E ulët', 'Mesatare', 'E lartë')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'}
login_failures = {}
schema_initialized = False

def get_db_connection():
    global schema_initialized
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE', 'complaint_db')
    )
    if not schema_initialized:
        cursor = connection.cursor()
        cursor.execute("SHOW COLUMNS FROM complaints")
        complaint_columns = {row[0] for row in cursor.fetchall()}
        if 'assigned_admin_id' not in complaint_columns:
            cursor.execute("ALTER TABLE complaints ADD COLUMN assigned_admin_id INT NULL")
        if 'due_at' not in complaint_columns:
            cursor.execute("ALTER TABLE complaints ADD COLUMN due_at DATETIME NULL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                used_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaint_comments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                complaint_id INT NOT NULL,
                user_id INT NOT NULL,
                comment TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
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
            )
        """)
        connection.commit()
        cursor.close()
        schema_initialized = True
    return connection

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

def send_reset_email(recipient, reset_url):
    sender = os.getenv('GMAIL_ADDRESS', '').strip()
    app_password = os.getenv('GMAIL_APP_PASSWORD', '').strip()
    if not sender or not app_password:
        app.logger.warning('Resetimi i fjalëkalimit nuk u dërgua: SMTP nuk është konfiguruar.')
        return False

    message = EmailMessage()
    message['Subject'] = 'Resetimi i fjalëkalimit'
    message['From'] = sender
    message['To'] = recipient
    message.set_content(
        "Për të ndryshuar fjalëkalimin, hapni këtë lidhje brenda 30 minutash:\n"
        f"{reset_url}\n\nNëse nuk e kërkuat ju këtë veprim, injorojeni këtë email."
    )
    try:
        with smtplib.SMTP(os.getenv('SMTP_HOST', 'smtp.gmail.com'),
                          int(os.getenv('SMTP_PORT', '587'))) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(sender, app_password)
            smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError, ValueError) as error:
        app.logger.error('Gabim në dërgimin e reset email-it: %s', error)
        return False

def send_status_email(complaint_id, recipient, status, admin_response=''):
    sender = os.getenv('GMAIL_ADDRESS', '').strip()
    app_password = os.getenv('GMAIL_APP_PASSWORD', '').strip()
    if not sender or not app_password or not recipient:
        return False

    message = EmailMessage()
    message['Subject'] = f"Ankesa #{complaint_id} u përditësua"
    message['From'] = sender
    message['To'] = recipient
    plain_text = (
        f"Statusi i ankesës #{complaint_id} është: {status}.\n"
    )
    if admin_response:
        plain_text += f"\nPërgjigjja e administratorit:\n{admin_response}\n"

    message.set_content(plain_text)
    try:
        with smtplib.SMTP(os.getenv('SMTP_HOST', 'smtp.gmail.com'),
                          int(os.getenv('SMTP_PORT', '587'))) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(sender, app_password)
            smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError, ValueError) as error:
        app.logger.error('Gabim në dërgimin e njoftimit të statusit: %s', error)
        return False

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

        failures = login_failures.get(email)
        if failures and failures['count'] >= 5:
            retry_at = failures['retry_at']
            if datetime.now() < retry_at:
                error = "Llogaria është bllokuar për disa minuta për shkak të shumë provave të dështuara."
                return render_template('login.html', error=error)
            login_failures.pop(email, None)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            login_failures.pop(email, None)
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session.permanent = True
            return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'index'))
        else:
            record = login_failures.setdefault(email, {'count': 0, 'retry_at': datetime.now()})
            record['count'] += 1
            if record['count'] >= 5:
                record['retry_at'] = datetime.now() + timedelta(minutes=10)
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

@app.route('/complaints/new', methods=['GET', 'POST'])
def create_complaint_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    error = None
    if request.method == 'POST':
        complaint_type = (request.form.get('complaint_type') or 'Online').strip()
        category_name = (request.form.get('category') or 'Tjetër').strip()
        priority = (request.form.get('priority') or 'Mesatare').strip()
        description = (request.form.get('description') or '').strip()

        if len(description) < 10:
            error = "Përshkrimi duhet të ketë të paktën 10 karaktere."
        elif priority not in VALID_PRIORITIES:
            error = "Niveli i urgjencës nuk është i vlefshëm."
        else:
            title = f"[{category_name}] Ankesë {complaint_type}"
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT id FROM categories WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                (category_name,)
            )
            category_row = cursor.fetchone()
            if not category_row:
                cursor.execute("SELECT id FROM categories ORDER BY id ASC LIMIT 1")
                category_row = cursor.fetchone()
            category_id = category_row['id'] if category_row else 1

            sla_hours = 24 if priority == 'E lartë' else 72 if priority == 'Mesatare' else 168
            due_at = datetime.now() + timedelta(hours=sla_hours)
            cursor.execute("""
                INSERT INTO complaints (
                    user_id, category_id, complaint_type, title, description,
                    status, priority, due_at
                )
                VALUES (%s, %s, %s, %s, %s, 'Në pritje', %s, %s)
            """, (
                session['user_id'], category_id, complaint_type, title, description,
                priority, due_at.strftime('%Y-%m-%d %H:%M:%S')
            ))
            complaint_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO complaint_status_history (complaint_id, status, changed_by)
                VALUES (%s, 'Në pritje', %s)
            """, (complaint_id, session['user_id']))

            uploaded_files = request.files.getlist('attachments')
            for uploaded in uploaded_files:
                if not uploaded or not uploaded.filename or not allowed_attachment(uploaded.filename):
                    continue
                original_name = secure_filename(uploaded.filename)
                stored_name = f"{secrets.token_hex(16)}_{original_name}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
                uploaded.save(file_path)
                size = os.path.getsize(file_path)
                cursor.execute("""
                    INSERT INTO complaint_attachments (
                        complaint_id, uploaded_by, original_name, stored_name, size
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (complaint_id, session['user_id'], original_name, stored_name, size))

            conn.commit()
            cursor.execute("SELECT full_name, email FROM users WHERE id = %s", (session['user_id'],))
            client = cursor.fetchone()
            cursor.close()
            conn.close()

            send_complaint_email(
                complaint_id,
                client['full_name'] if client else session.get('full_name', 'Klient'),
                client['email'] if client else '',
                category_name,
                complaint_type,
                priority,
                description
            )
            return redirect(url_for('index'))

    cursor = None
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name FROM categories ORDER BY name ASC")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('create_complaint.html', categories=categories, error=error)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            token_hash = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 30 MINUTE))
            """, (user['id'], token_hash))
            conn.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            send_reset_email(user['email'], reset_url)
        cursor.close()
        conn.close()
        message = "Nëse email-i ekziston, ju është dërguar një lidhje resetimi."
    return render_template('forgot_password.html', message=message)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '').encode('utf-8')
        if len(password) < 8:
            error = "Fjalëkalimi duhet të ketë të paktën 8 karaktere."
        else:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, user_id, token_hash
                FROM password_reset_tokens
                WHERE expires_at > NOW() AND used_at IS NULL
            """)
            valid_user_id = None
            for record in cursor.fetchall():
                if bcrypt.checkpw(token.encode('utf-8'), record['token_hash'].encode('utf-8')):
                    valid_user_id = record['user_id']
                    break
            if not valid_user_id:
                cursor.close()
                conn.close()
                error = "Lidhja është e pavlefshme ose ka skaduar."
            else:
                hashed = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
                cursor.execute("UPDATE users SET password = %s WHERE id = %s",
                               (hashed, valid_user_id))
                cursor.execute("""
                    UPDATE password_reset_tokens
                    SET used_at = NOW()
                    WHERE user_id = %s AND used_at IS NULL
                """, (valid_user_id,))
                conn.commit()
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
    return render_template('reset_password.html', error=error)

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
               c.assigned_admin_id, c.due_at,
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
    sla_hours = 24 if priority == 'E lartë' else 72 if priority == 'Mesatare' else 168
    due_at = datetime.now() + timedelta(hours=sla_hours)

    cursor.execute("""
        INSERT INTO complaints (
            user_id, category_id, complaint_type, title, description,
            status, priority, due_at
        )
        VALUES (%s, %s, %s, %s, %s, 'Në pritje', %s, %s)
    """, (session['user_id'], category_id, complaint_type, title, description, priority,
          due_at.strftime('%Y-%m-%d %H:%M:%S')))
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
    cursor.execute("SELECT id, full_name FROM users WHERE role = 'admin' ORDER BY full_name ASC")
    admins = cursor.fetchall()

    base_sql = """
        SELECT c.id, c.title, c.description, c.status, c.priority,
               COALESCE(cat.name, 'Tjetër') AS category_name,
               COALESCE(c.complaint_type, 'Online') AS complaint_type,
               COALESCE(c.admin_response, '') AS admin_response,
               c.assigned_admin_id, c.due_at,
               DATE_FORMAT(c.created_at, '%d/%m/%Y') AS created_date,
               DATE_FORMAT(c.created_at, '%H:%i') AS created_time,
               u.full_name,
               COALESCE(ad.full_name, 'Pa caktuar') AS assigned_admin_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN categories cat ON c.category_id = cat.id
        LEFT JOIN users ad ON c.assigned_admin_id = ad.id
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
        categories=categories,
        admins=admins
    )

@app.route('/api/complaints/<int:complaint_id>/comment', methods=['POST'])
def save_complaint_comment(complaint_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip()
    if not comment:
        return jsonify({'error': 'Komenti nuk mund të jetë bosh.'}), 400
    if len(comment) > 2000:
        return jsonify({'error': 'Komenti është shumë i gjatë.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET admin_response = %s WHERE id = %s", (comment, complaint_id))
    cursor.execute("""
        INSERT INTO complaint_comments (complaint_id, user_id, comment)
        VALUES (%s, %s, %s)
    """, (complaint_id, session['user_id'], comment))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'comment': comment})

@app.route('/api/complaints/<int:complaint_id>/comments', methods=['GET'])
def get_complaint_comments(complaint_id):
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
        SELECT cc.comment, cc.created_at,
               u.full_name, u.role
        FROM complaint_comments cc
        JOIN users u ON cc.user_id = u.id
        WHERE cc.complaint_id = %s
        ORDER BY cc.created_at ASC, cc.id ASC
    """, (complaint_id,))
    comments = cursor.fetchall()
    cursor.close()
    conn.close()
    for comment in comments:
        comment['created_at'] = comment['created_at'].strftime('%d/%m/%Y %H:%M')
    return jsonify(comments)

@app.route('/resolve/<int:id>', methods=['POST'])
def resolve_complaint(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.status, c.admin_response, u.email
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = %s
    """, (id,))
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
    if complaint and complaint['status'] != 'Zgjidhur':
        send_status_email(id, complaint['email'], 'Zgjidhur', complaint['admin_response'] or '')
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
    cursor.execute("""
        SELECT c.status, c.admin_response, u.email
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = %s
    """, (complaint_id,))
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
    send_status_email(complaint_id, complaint['email'], status, complaint['admin_response'] or '')
    return jsonify({'success': True, 'status': status})

@app.route('/api/complaints/<int:complaint_id>/assignment', methods=['POST'])
def update_complaint_assignment(complaint_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    admin_id = data.get('assigned_admin_id')
    due_at = (data.get('due_at') or '').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    admin_ids = {str(row['id']) for row in cursor.fetchall()}

    updates = []
    params = []
    if admin_id is not None:
        if str(admin_id) == '' or str(admin_id) == '0':
            updates.append("assigned_admin_id = NULL")
        elif str(admin_id) in admin_ids:
            updates.append("assigned_admin_id = %s")
            params.append(int(admin_id))
        else:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Administratori nuk është i vlefshëm.'}), 400

    if due_at:
        try:
            parsed_due = datetime.strptime(due_at, '%Y-%m-%dT%H:%M')
        except ValueError:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Afati nuk është i vlefshëm.'}), 400
        updates.append("due_at = %s")
        params.append(parsed_due.strftime('%Y-%m-%d %H:%M:%S'))

    if not updates:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Nuk u dhanë ndryshime.'}), 400

    params.append(complaint_id)
    cursor.execute(
        "UPDATE complaints SET " + ", ".join(updates) + " WHERE id = %s",
        tuple(params)
    )
    conn.commit()

    cursor.execute("""
        SELECT u.email
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = %s
    """, (complaint_id,))
    owner = cursor.fetchone()
    cursor.close()
    conn.close()

    if owner:
        send_status_email(
            complaint_id,
            owner['email'],
            'Ankesa u ricaktua ose afati u përditësua.'
        )
    return jsonify({'success': True})

@app.route('/api/complaints/<int:complaint_id>/comments', methods=['POST'])
def add_complaint_comment(complaint_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    comment = (data.get('comment') or '').strip()
    if not comment:
        return jsonify({'error': 'Komenti nuk mund të jetë bosh.'}), 400
    if len(comment) > 2000:
        return jsonify({'error': 'Komenti është shumë i gjatë.'}), 400

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
        INSERT INTO complaint_comments (complaint_id, user_id, comment)
        VALUES (%s, %s, %s)
    """, (complaint_id, session['user_id'], comment))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'comment': comment}), 201

@app.route('/api/complaints/<int:complaint_id>', methods=['PUT'])
def update_owned_complaint(complaint_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    description = (data.get('description') or '').strip()
    priority = (data.get('priority') or '').strip()
    if len(description) < 10:
        return jsonify({'error': 'Përshkrimi duhet të ketë të paktën 10 karaktere.'}), 400
    if priority not in VALID_PRIORITIES:
        return jsonify({'error': 'Prioriteti nuk është i vlefshëm.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, status FROM complaints WHERE id = %s", (complaint_id,))
    complaint = cursor.fetchone()
    if not complaint:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Ankesa nuk u gjet.'}), 404
    if complaint['user_id'] != session['user_id']:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Forbidden'}), 403
    if complaint['status'] != 'Në pritje':
        cursor.close()
        conn.close()
        return jsonify({'error': 'Ankesa nuk mund të modifikohet pasi ka filluar trajtimi.'}), 409

    cursor.execute("UPDATE complaints SET description = %s, priority = %s WHERE id = %s",
                   (description, priority, complaint_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

def allowed_attachment(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/complaints/<int:complaint_id>/attachments', methods=['GET'])
def get_complaint_attachments(complaint_id):
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
        SELECT id, original_name, size, created_at
        FROM complaint_attachments
        WHERE complaint_id = %s
        ORDER BY created_at DESC
    """, (complaint_id,))
    attachments = cursor.fetchall()
    cursor.close()
    conn.close()
    for attachment in attachments:
        attachment['created_at'] = attachment['created_at'].strftime('%d/%m/%Y %H:%M')
    return jsonify(attachments)

@app.route('/api/complaints/<int:complaint_id>/attachments', methods=['POST'])
def upload_complaint_attachment(complaint_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    uploaded = request.files.get('file')
    if not uploaded or not uploaded.filename:
        return jsonify({'error': 'Zgjidhni një skedar.'}), 400
    if not allowed_attachment(uploaded.filename):
        return jsonify({'error': 'Lloji i skedarit nuk lejohet.'}), 400

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

    original_name = secure_filename(uploaded.filename)
    stored_name = f"{secrets.token_hex(16)}_{original_name}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
    uploaded.save(file_path)
    size = os.path.getsize(file_path)

    cursor.execute("""
        INSERT INTO complaint_attachments (
            complaint_id, uploaded_by, original_name, stored_name, size
        ) VALUES (%s, %s, %s, %s, %s)
    """, (complaint_id, session['user_id'], original_name, stored_name, size))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'filename': original_name}), 201

@app.route('/api/attachments/<int:attachment_id>', methods=['GET'])
def download_attachment(attachment_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ca.stored_name, ca.original_name, c.user_id
        FROM complaint_attachments ca
        JOIN complaints c ON ca.complaint_id = c.id
        WHERE ca.id = %s
    """, (attachment_id,))
    attachment = cursor.fetchone()
    cursor.close()
    conn.close()
    if not attachment:
        return jsonify({'error': 'Skedari nuk u gjet.'}), 404
    if session.get('role') != 'admin' and attachment['user_id'] != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        attachment['stored_name'],
        as_attachment=True,
        download_name=attachment['original_name']
    )

@app.route('/api/complaints/<int:complaint_id>', methods=['DELETE'])
def delete_owned_complaint(complaint_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, status FROM complaints WHERE id = %s", (complaint_id,))
    complaint = cursor.fetchone()
    if not complaint:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Ankesa nuk u gjet.'}), 404
    if complaint['user_id'] != session['user_id']:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Forbidden'}), 403
    if complaint['status'] != 'Në pritje':
        cursor.close()
        conn.close()
        return jsonify({'error': 'Ankesa nuk mund të fshihet pasi ka filluar trajtimi.'}), 409

    cursor.execute("DELETE FROM complaints WHERE id = %s", (complaint_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

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
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
