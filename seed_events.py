import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "db.sqlite")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# чтобы не дублировать, посмотрим, есть ли уже события по Глазову
cur.execute("SELECT COUNT(*) FROM events WHERE city = ?", ("Глазов",))
count = cur.fetchone()[0]

if count == 0:
    events = [
        (
            "Эко-субботник “Чистый берег Чепцы”",
            "Экология и природа",
            "Глазов",
            "Глазов, Заречный парк",
            "23 ноября",
            "11:00–14:00",
            "/img/event-clean-river.png",
        ),
        (
            "Творческая мастерская “Тёплые открытки”",
            "Культура",
            "Глазов",
            "Глазов, Дом детского творчества",
            "30 ноября",
            "13:00–16:00",
            "/img/event-warm-cards.png",
        ),
        (
            "Помощь в организации спорта для людей с ОВЗ",
            "Спорт, Люди с ОВЗ",
            "Глазов",
            "Глазов, спорткомплекс “Глазов Арена”",
            "27 ноября",
            "18:00–20:00",
            "/img/event-sport-ovz.png",
        ),
    ]

    for title, category, city, address, date, time, image in events:
        cur.execute(
            """
            INSERT INTO events (title, category, city, address, date, time, image, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                category,
                city,
                address,
                date,
                time,
                image,
                datetime.utcnow().isoformat(),
            ),
        )

    conn.commit()
    print(f"Добавлено фейковых мероприятий: {len(events)}")
else:
    print(f"В БД уже есть {count} мероприятий с city='Глазов', ничего не добавляю.")

conn.close()