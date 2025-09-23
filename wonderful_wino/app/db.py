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
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
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

def add_or_update_wine(wine_data: dict, quantity: int, cost_tier: int):
    """
    Inserts new wine data or updates quantity and details if it already exists.
    Returns True on success, False on failure.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, quantity FROM wines WHERE vivino_url = ?", (wine_data['vivino_url'],))
        existing_wine = cursor.fetchone()

        if existing_wine:
            wine_id, current_quantity = existing_wine
            new_quantity = current_quantity + quantity
            cursor.execute('''
                UPDATE wines SET quantity = ?, name = ?, vintage = ?, varietal = ?, region = ?,
                country = ?, vivino_rating = ?, image_url = ?, cost_tier = ?, added_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                new_quantity, wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                wine_data['image_url'], cost_tier, wine_id
            ))
            logger.info(f"Updated quantity for '{wine_data['name']}' to {new_quantity}.")
            conn.commit()
            return True
        else:
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, image_url, quantity, cost_tier, personal_rating, tasting_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wine_data['vivino_url'], wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                wine_data['image_url'], quantity, cost_tier, None, None
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
    """Fetches all wines based on a filter. Returns a list of dictionaries."""
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
    """Fetches a single wine record by vivino URL. Returns a dictionary or None."""
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
    """Updates all details for a specific wine."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, 
            quantity = ?, cost_tier = ?, personal_rating = ?, tasting_notes = ? 
            WHERE vivino_url = ?
        ''', (name, vintage, varietal, region, country, quantity, cost_tier, personal_rating, tasting_notes, vivino_url))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Updated all details for wine: {name} ({vintage})")
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error updating wine details: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_wine_quantity(vivino_url, new_quantity):
    """Updates the quantity of a specific wine."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Updated quantity for {vivino_url} to {new_quantity}")
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error updating wine quantity: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_personal_rating(vivino_url, rating):
    """Updates the personal rating of a specific wine."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET personal_rating = ? WHERE vivino_url = ?", (rating, vivino_url))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Updated personal rating for {vivino_url} to {rating}")
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error updating personal rating: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_wine_notes_and_image(vivino_url, notes, image_url):
    """Updates tasting notes and image URL for a wine."""
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
            if cursor.rowcount > 0:
                logger.info(f"Updated notes and/or image for {vivino_url}")
                return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error updating notes/image: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def delete_wine_by_url(vivino_url):
    """Deletes a wine record from the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Deleted wine with URL: {vivino_url}")
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_wine_quantity_and_rating(vivino_url, new_quantity, personal_rating):
    """
    Updates both the quantity and personal rating of a wine.
    Returns the updated wine record as a dictionary or None on failure.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if personal_rating is not None:
            cursor.execute("UPDATE wines SET quantity = ?, personal_rating = ? WHERE vivino_url = ?", (new_quantity, personal_rating, vivino_url))
            logger.info(f"Updated quantity to {new_quantity} and rating to {personal_rating} for {vivino_url}")
        else:
            cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
            logger.info(f"Updated quantity to {new_quantity} for {vivino_url}")
        conn.commit()
        
        # Re-fetch the updated row to return
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        updated_wine = cursor.fetchone()
        
        return dict(updated_wine) if updated_wine else None
        
    except sqlite3.Error as e:
        logger.error(f"Database error updating quantity and rating: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def get_settings():
    """Retrieves all settings from the settings table."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        settings_dict = {row['key']: row['value'] for row in rows}
        return settings_dict
    except sqlite3.Error as e:
        logger.error(f"Database error getting settings: {e}")
        return {}
    finally:
        if conn:
            conn.close()

def update_settings(data):
    """Saves or updates settings in the settings table."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for key, value in data.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        logger.info("Settings updated successfully.")
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
    """Creates a safe backup of the database to the /share directory."""
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
        return False, "Database backup failed. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        return False, "An unexpected error occurred during backup."
    finally:
        if conn:
            conn.close()
        if backup_conn:
            backup_conn.close()

def restore_database():
    """Restores the database from a backup file in the /share directory."""
    conn = None
    backup_conn = None
    try:
        backup_dir = os.path.dirname(DB_PATH)
        backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")
        if not os.path.exists(backup_path):
            logger.warning(f"Restore failed: Backup file not found at {backup_path}")
            return False, "Backup file not found."
        source_conn = sqlite3.connect(backup_path)
        dest_conn = get_db_connection()
        with dest_conn:
            source_conn.backup(dest_conn)
        source_conn.close()
        logger.info("Database restored successfully.")
        return True, "Database restored successfully. The page will now refresh."
    except sqlite3.Error as e:
        logger.error(f"Database restore failed: {e}")
        return False, "Database restore failed. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error during restore: {e}")
        return False, "An unexpected error occurred during restore."
    finally:
        if conn:
            conn.close()
        if backup_conn:
            backup_conn.close()

def get_wine_by_name_and_vintage(name, vintage):
    """Fetches a single wine by its name and vintage."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if vintage is not None:
            cursor.execute("SELECT * FROM wines WHERE LOWER(name) = LOWER(?) AND vintage = ?", (name, vintage))
        else:
            cursor.execute("SELECT * FROM wines WHERE LOWER(name) = LOWER(?) AND vintage IS NULL", (name,))
        wine = cursor.fetchone()
        return dict(wine) if wine else None
    except sqlite3.Error as e:
        logger.error(f"Database error getting wine by name/vintage: {e}")
        return None
    finally:
        if conn:
            conn.close()
