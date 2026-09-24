import os
import sqlite3

# Vercel environment check: Serverless runtime par '/tmp' directory writable hoti hai
if os.environ.get('VERCEL'):
    DB_PATH = '/tmp/database.db'
else:
    DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Students Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        branch TEXT,
        skills TEXT,
        password TEXT
    )
    ''')

    # Resume History Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS resume_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        score INTEGER,
        skills TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print(f"Database Created/Initialized Successfully at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
