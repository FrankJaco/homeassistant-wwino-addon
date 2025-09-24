import sqlite3
import logging
from .config import DB_PATH
import os

logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes and returns a database connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = None
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vivino_url TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                vintage INTEGER,
                varietal TEXT,
                region TEXT,
                country TEXT,
                vivino_rating REAL,
                image_url TEXT,
                quantity INTEGER DEFAULT 1,
                cost_tier INTEGER,
                personal_rating REAL,
                tasting_notes TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                needs_review BOOLEAN DEFAULT FALSE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consumption_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wine_id INTEGER NOT NULL,
                consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                personal_rating REAL,
                FOREIGN KEY (wine_id) REFERENCES wines (id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()

def reinitialize_database():
    """Drops all existing tables and then recreates them by calling init_db()."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.warning("Reinitializing database: Dropping existing tables.")
        cursor.execute("DROP TABLE IF EXISTS consumption_history")
        cursor.execute("DROP TABLE IF EXISTS wines")
        cursor.execute("DROP TABLE IF EXISTS settings")
        conn.commit()
        init_db()
        logger.info("Database tables re-created.")
    except sqlite3.Error as e:
        logger.error(f"Database error during reinitialization: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def add_consumption_record(wine_id, personal_rating):
    """Adds a new record to the consumption_history table."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO consumption_history (wine_id, personal_rating) VALUES (?, ?)",
            (wine_id, personal_rating)
        )
        conn.commit()
        logger.info(f"Added consumption record for wine_id: {wine_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error adding consumption record: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# NEW FUNCTION to get the consumption history for a specific wine
def get_consumption_history(wine_id: int):
    """Fetches all consumption records for a given wine_id."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM consumption_history WHERE wine_id = ? ORDER BY consumed_at DESC",
            (wine_id,)
        )
        history = cursor.fetchall()
        return [dict(row) for row in history]
    except sqlite3.Error as e:
        logger.error(f"Database error getting consumption history: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- (All other functions remain the same) ---

def add_or_update_wine(wine_data: dict, quantity: int, cost_tier: int):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, quantity FROM wines WHERE vivino_url = ?", (wine_data['vivino_url'],))
        existing_wine = cursor.fetchone()
        needs_review_flag = wine_data.get('name', '').startswith(('Review Wine', 'Vivino Wine ID'))

        if existing_wine:
            wine_id, current_quantity = existing_wine
            new_quantity = current_quantity + quantity
            cursor.execute('''
                UPDATE wines SET quantity = ?, name = ?, vintage = ?, varietal = ?, region = ?,
                country = ?, vivino_rating = ?, image_url = ?, cost_tier = ?, needs_review = ?
                WHERE id = ?
            ''', (
                new_quantity, wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                wine_data['image_url'], cost_tier, needs_review_flag, wine_id
            ))
            logger.info(f"Updated quantity for '{wine_data['name']}' to {new_quantity}.")
        else:
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, image_url, quantity, cost_tier, personal_rating, tasting_notes, needs_review)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wine_data['vivino_url'], wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                wine_data['image_url'], quantity, cost_tier, None, None, needs_review_flag
            ))
            logger.info(f"New wine '{wine_data['name']}' inserted with quantity {quantity}.")
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error inserting/updating wine data: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_all_wines(status_filter: str = 'on_hand'):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM wines"
        if status_filter == 'on_hand':
            query += " WHERE quantity > 0"
        elif status_filter == 'history':
            query += " WHERE quantity = 0"
        query += " ORDER BY added_at DESC"
        cursor.execute(query)
        wines = cursor.fetchall()
        return [dict(wine) for wine in wines]
    except sqlite3.Error as e:
        logger.error(f"Database error getting all wines: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_wine_by_url(vivino_url: str):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine = cursor.fetchone()
        return dict(wine) if wine else None
    except sqlite3.Error as e:
        logger.error(f"Database error getting wine by URL: {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_wine_details(vivino_url, name, vintage, quantity, varietal, region, country, cost_tier, personal_rating, tasting_notes):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, 
            quantity = ?, cost_tier = ?, personal_rating = ?, tasting_notes = ?, needs_review = FALSE 
            WHERE vivino_url = ?
        ''', (name, vintage, varietal, region, country, quantity, cost_tier, personal_rating, tasting_notes, vivino_url))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating wine details: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_wine_quantity(vivino_url, new_quantity):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating wine quantity: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_personal_rating(vivino_url, rating):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET personal_rating = ? WHERE vivino_url = ?", (rating, vivino_url))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating personal rating: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_wine_notes_and_image(vivino_url, notes, image_url):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []
        if notes is not None:
            updates.append("tasting_notes = ?")
            params.append(notes)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if updates:
            query = f"UPDATE wines SET {', '.join(updates)} WHERE vivino_url = ?"
            params.append(vivino_url)
            cursor.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount > 0
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error updating notes/image: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def delete_wine_by_url(vivino_url):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_wine_quantity_and_rating(vivino_url, new_quantity, personal_rating):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if personal_rating is not None:
            cursor.execute("UPDATE wines SET quantity = ?, personal_rating = ? WHERE vivino_url = ?", (new_quantity, personal_rating, vivino_url))
        else:
            cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
        conn.commit()
        return get_wine_by_url(vivino_url)
    except sqlite3.Error as e:
        logger.error(f"Database error updating quantity and rating: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def get_settings():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        return {row['key']: row['value'] for row in rows}
    except sqlite3.Error as e:
        logger.error(f"Database error getting settings: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def update_settings(data):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for key, value in data.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error updating settings: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def backup_database():
    conn = None
    backup_conn = None
    try:
        backup_dir = os.path.dirname(DB_PATH)
        backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")
        source_conn = get_db_connection()
        backup_conn = sqlite3.connect(backup_path)
        with backup_conn:
            source_conn.backup(backup_conn)
        source_conn.close()
        logger.info(f"Database backup completed successfully to {backup_path}.")
        return True, f"Backup successful! File saved in {backup_dir}."
    except sqlite3.Error as e:
        logger.error(f"Database backup failed: {e}")
        return False, "Database backup failed."
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        return False, "An unexpected error occurred."
    finally:
        if conn: conn.close()
        if backup_conn: backup_conn.close()

def restore_database():
    conn = None
    backup_conn = None
    try:
        backup_dir = os.path.dirname(DB_PATH)
        backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")
        if not os.path.exists(backup_path):
            return False, "Backup file not found."
        source_conn = sqlite3.connect(backup_path)
        dest_conn = get_db_connection()
        with dest_conn:
            source_conn.backup(dest_conn)
        source_conn.close()
        return True, "Database restored successfully."
    except sqlite3.Error as e:
        logger.error(f"Database restore failed: {e}")
        return False, "Database restore failed."
    except Exception as e:
        logger.error(f"Unexpected error during restore: {e}")
        return False, "An unexpected error occurred."
    finally:
        if conn: conn.close()
        if backup_conn: backup_conn.close()

def get_wine_by_name_and_vintage(name, vintage):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if vintage is not None:
            cursor.execute("SELECT * FROM wines WHERE name = ? AND vintage = ?", (name, vintage))
        else:
            cursor.execute("SELECT * FROM wines WHERE name = ? AND vintage IS NULL", (name,))
        wine = cursor.fetchone()
        return dict(wine) if wine else None
    except sqlite3.Error as e:
        logger.error(f"Database error getting wine by name/vintage: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_all_historical_wines():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM wines"
        cursor.execute(query)
        wines = cursor.fetchall()
        return [dict(wine) for wine in wines]
    except sqlite3.Error as e:
        logger.error(f"Database error getting historical wines: {e}")
        return []
    finally:
        if conn:
            conn.close()