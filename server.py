import os
import uuid
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(__file__)
FRONT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
DB_PATH = os.path.join(BASE_DIR, "db.sqlite")

app = Flask(
    __name__,
    static_folder=FRONT_DIR,     # здесь index.html + css + js
    static_url_path=""          # пути /css/... /js/... работают
)


# ========================= DB HELPERS =========================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            accountType TEXT NOT NULL DEFAULT 'person', -- person | nko
            created_at TEXT NOT NULL
        );
    """)

    # токены сессий
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)

    # таблица НКО
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nko (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            volunteers TEXT,
            phone TEXT,
            address TEXT,
            logo TEXT,
            website TEXT,
            albums TEXT,
            filters TEXT,
            city TEXT,
            lat REAL,
            lng REAL,
            status TEXT NOT NULL DEFAULT 'approved', -- approved | pending | rejected
            created_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (created_by_user_id) REFERENCES users (id)
        );
    """)

    # таблица мероприятий
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,
            city TEXT,
            address TEXT,
            date TEXT,
            time TEXT,
            image TEXT,
            created_at TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# ========================= AUTH HELPERS =========================

def create_session(user_id: int) -> str:
    token = uuid.uuid4().hex
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (user_id, token, created_at) VALUES (?, ?, ?)",
        (user_id, token, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return token


def get_token_from_header():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip() or None


def get_current_user():
    token = get_token_from_header()
    if not token:
        return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row_to_dict(row)


# ========================= ROUTES: AUTH =========================

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    account_type = data.get("accountType") or "person"

    if not email or not password:
        return jsonify({"message": "Email и пароль обязательны"}), 400

    if account_type not in ("person", "nko"):
        account_type = "person"

    password_hash = generate_password_hash(password)

    conn = get_db()
    cur = conn.cursor()

    # проверяем, что email свободен
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        return jsonify({"message": "Пользователь с таким email уже существует"}), 400

    cur.execute("""
        INSERT INTO users (name, email, password_hash, accountType, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (name, email, password_hash, account_type, datetime.utcnow().isoformat()))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    token = create_session(user_id)

    user = {
        "id": user_id,
        "name": name,
        "email": email,
        "accountType": account_type
    }

    return jsonify({"user": user, "token": token})

@app.route("/api/events", methods=["GET"])
def list_events():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, category, city, address, date, time, image
        FROM events
        ORDER BY date
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "city": r["city"],
            "address": r["address"],
            "date": r["date"],
            "time": r["time"],
            "image": r["image"],     # путь вида /img/events/eco1.jpg
        })

    return jsonify(result)

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"message": "Email и пароль обязательны"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"message": "Неверный email или пароль"}), 401

    if not check_password_hash(row["password_hash"], password):
        return jsonify({"message": "Неверный email или пароль"}), 401

    token = create_session(row["id"])

    user = {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "accountType": row["accountType"]
    }

    return jsonify({"user": user, "token": token})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    if not user:
        return jsonify({"message": "Не авторизован"}), 401

    return jsonify({
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "accountType": user["accountType"]
        }
    })


# ========================= ROUTES: NKO =========================

@app.route("/api/nko", methods=["GET"])
def list_nko():
    """
    Отдаём только НКО со статусом 'approved'
    Используется картой и фильтрами на фронте.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, category, description, volunteers, phone,
               address, logo, website, albums, filters, city, lat, lng, status
        FROM nko
        WHERE status = 'approved'
        ORDER BY name COLLATE NOCASE
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "description": r["description"],
            "volunteers": r["volunteers"],
            "phone": r["phone"],
            "address": r["address"],
            "logo": r["logo"],
            "website": r["website"],
            "albums": r["albums"],
            "filters": r["filters"],
            "city": r["city"],
            "lat": r["lat"],
            "lng": r["lng"],
            "status": r["status"]
        })

    return jsonify(result)

@app.route("/")
def index():
    # отдаём index.html из корня проекта (/Users/roman/Downloads/NKO)
    return send_from_directory(FRONT_DIR, "index.html")

@app.route("/api/nko", methods=["POST"])
def create_nko():
    """
    Создание новой НКО пользователем.
    Запись уходит со статусом 'pending' (на модерацию).
    """
    user = get_current_user()
    if not user:
        return jsonify({"message": "Требуется авторизация"}), 401

    data = request.get_json(force=True, silent=True) or {}

    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    description = (data.get("description") or "").strip()
    volunteers = (data.get("volunteers") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    city = (data.get("city") or "").strip()
    website = (data.get("website") or "").strip()
    logo = (data.get("logo") or "").strip()
    filters = (data.get("filters") or "").strip()

    # координаты можно в будущем геокодить; пока берём, если прислали
    lat = data.get("lat")
    lng = data.get("lng")

    if not name or not category or not description or not city:
        return jsonify({"message": "Заполните обязательные поля: название, категория, описание, город"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO nko (
            name, category, description, volunteers, phone, address, logo,
            website, albums, filters, city, lat, lng, status,
            created_by_user_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name, category, description, volunteers or description, phone, address, logo,
        website, "", filters, city, lat, lng, "pending",
        user["id"], datetime.utcnow().isoformat()
    ))

    new_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "id": new_id,
        "message": "НКО отправлена на модерацию"
    }), 201


# ========================= ENTRYPOINT =========================

if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    # Для разработки:
    app.run(host="0.0.0.0", port=5000, debug=True)