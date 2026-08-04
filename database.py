import sqlite3
from datetime import datetime
from config import DATABASE_NAME


def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            type TEXT DEFAULT 'call',
            summary TEXT,
            agreements TEXT,
            next_action TEXT,
            reminder_date TIMESTAMP,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id INTEGER,
            reminder_text TEXT,
            reminder_date TIMESTAMP,
            is_sent BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (interaction_id) REFERENCES interactions(id)
        )
    ''')

    conn.commit()
    conn.close()


def add_client(name, phone=None, company=None, notes=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clients (name, phone, company, notes) VALUES (?, ?, ?, ?)",
        (name, phone, company, notes)
    )
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id


def get_client_by_name(name):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE name LIKE ?", (f"%{name}%",))
    result = cursor.fetchall()
    conn.close()
    return result


def get_client_by_id(client_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    result = cursor.fetchone()
    conn.close()
    return result


def get_all_clients():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
    result = cursor.fetchall()
    conn.close()
    return result


def add_interaction(client_id, summary, agreements, next_action, reminder_date=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO interactions
           (client_id, summary, agreements, next_action, reminder_date)
           VALUES (?, ?, ?, ?, ?)""",
        (client_id, summary, agreements, next_action, reminder_date)
    )
    interaction_id = cursor.lastrowid

    if reminder_date:
        cursor.execute(
            """INSERT INTO reminders
               (interaction_id, reminder_text, reminder_date)
               VALUES (?, ?, ?)""",
            (interaction_id, f"Позвонить клиенту. Договорились: {agreements}", reminder_date)
        )

    conn.commit()
    conn.close()
    return interaction_id


def get_pending_reminders():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """SELECT r.id, r.reminder_text, r.reminder_date, c.name
           FROM reminders r
           JOIN interactions i ON r.interaction_id = i.id
           JOIN clients c ON i.client_id = c.id
           WHERE r.is_sent = 0 AND r.reminder_date <= ?""",
        (now,)
    )
    result = cursor.fetchall()
    conn.close()
    return result


def mark_reminder_sent(reminder_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


def get_client_history(client_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT i.created_at, i.summary, i.agreements, i.next_action, i.reminder_date
           FROM interactions i
           WHERE i.client_id = ?
           ORDER BY i.created_at DESC""",
        (client_id,)
    )
    result = cursor.fetchall()
    conn.close()
    return result


def get_last_interaction(client_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT agreements FROM interactions
           WHERE client_id = ? ORDER BY created_at DESC LIMIT 1""",
        (client_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_statistics():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM clients")
    total_clients = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM interactions")
    total_interactions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE is_sent = 0")
    pending_reminders = cursor.fetchone()[0]
    conn.close()
    return {
        "total_clients": total_clients,
        "total_interactions": total_interactions,
        "pending_reminders": pending_reminders
    }