import sqlite3
import logging
from .config import DB_PATH

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
    Returns the updated wine record as a dictionary or None on failure.
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
            return get_wine_by_url(wine_data['vivino_url'])
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
            return get_wine_by_url(wine_data['vivino_url'])
    except sqlite3.Error as e:
        logger.error(f"Database error inserting/updating wine data: {e}")
        if conn:
            conn.rollback()
        return None
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

def update_wine_details(data: dict):
    """Updates various details of a wine record."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, 
            quantity = ?, cost_tier = ?, personal_rating = ?, tasting_notes = ? WHERE vivino_url = ?
        ''', (
            data.get('name'), data.get('vintage'), data.get('varietal'),
            data.get('region'), data.get('country'), data.get('quantity'),
            data.get('cost_tier'), data.get('personal_rating'), data.get('tasting_notes'),
            data.get('vivino_url')
        ))
        conn.commit()
        return get_wine_by_url(data.get('vivino_url'))
    except sqlite3.Error as e:
        logger.error(f"Database error updating wine details: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def set_wine_quantity(vivino_url: str, new_quantity: int):
    """Updates the quantity of a specific wine."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error setting wine quantity: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
            
def consume_wine_by_name_vintage(item_text: str, personal_rating: float):
    """Decrements quantity and adds rating based on name and vintage from webhook."""
    conn = None
    try:
        parsed_name, parsed_vintage = None, None
        if item_text.endswith(')') and item_text[-6:-5] == '(' and item_text[-5:-1].isdigit():
            try:
                parsed_vintage = int(item_text[-5:-1])
                parsed_name = item_text[:-6].rstrip()
            except (ValueError, IndexError):
                parsed_name = item_text.strip()
        else:
            parsed_name = item_text.strip()
            
        conn = get_db_connection()
        cursor = conn.cursor()

        if parsed_vintage is not None:
            query = "SELECT * FROM wines WHERE LOWER(name) = LOWER(?) AND vintage = ?"
            params = (parsed_name, parsed_vintage)
        else:
            query = "SELECT * FROM wines WHERE LOWER(name) = LOWER(?) AND vintage IS NULL"
            params = (parsed_name,)
        
        cursor.execute(query, params)
        wine_record = cursor.fetchone()

        if wine_record:
            wine_data_dict = dict(wine_record)
            current_db_quantity = wine_data_dict.get('quantity', 0)
            if current_db_quantity > 0:
                new_quantity = current_db_quantity - 1
                
                update_query = "UPDATE wines SET quantity = ?"
                update_params = [new_quantity]

                if personal_rating is not None:
                    try:
                        rating_val = float(personal_rating)
                        update_query += ", personal_rating = ?"
                        update_params.append(rating_val)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid rating value '{personal_rating}' received. Ignoring.")

                update_query += " WHERE id = ?"
                update_params.append(wine_data_dict['id'])
                
                cursor.execute(update_query, tuple(update_params))
                conn.commit()
                return get_wine_by_url(wine_data_dict['vivino_url'])
        return None
    except sqlite3.Error as e:
        logger.error(f"Database error consuming wine by name/vintage: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()
            
def consume_wine_by_url(vivino_url: str, personal_rating: float):
    """Decrements quantity and adds rating based on vivino URL."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()
        if not wine_data_row: return None
        
        wine_data_dict = dict(wine_data_row)
        current_quantity = wine_data_dict['quantity']
        if current_quantity > 0:
            new_quantity = current_quantity - 1
            if personal_rating is not None:
                cursor.execute("UPDATE wines SET quantity = ?, personal_rating = ? WHERE vivino_url = ?", (new_quantity, personal_rating, vivino_url))
            else:
                cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
            conn.commit()
            updated_wine = get_wine_by_url(vivino_url)
            return {'new_quantity': updated_wine['quantity']} # Return a simplified dict
    except sqlite3.Error as e:
        logger.error(f"Database error consuming wine by URL: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()
            
def delete_wine_by_url(vivino_url: str):
    """Deletes a wine record by vivino URL."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()
            
def rate_wine_by_url(vivino_url: str, personal_rating: float):
    """Updates the personal rating of a wine record."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET personal_rating = ? WHERE vivino_url = ?", (personal_rating, vivino_url))
        conn.commit()
        if cursor.rowcount > 0:
            return get_wine_by_url(vivino_url)
        return None
    except sqlite3.Error as e:
        logger.error(f"Database error rating wine: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()

def update_wine_notes(data: dict):
    """Updates tasting notes and image URL."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []
        if 'tasting_notes' in data:
            updates.append("tasting_notes = ?")
            params.append(data['tasting_notes'])
        if 'image_url' in data:
            updates.append("image_url = ?")
            params.append(data['image_url'])
        if not updates: return True # No changes
        query = f"UPDATE wines SET {', '.join(updates)} WHERE vivino_url = ?"
        params.append(data['vivino_url'])
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error saving notes: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()
            
def backup_database():
    """Creates a safe backup of the database."""
    conn = None
    try:
        backup_path = "/data/wonderful_wino_backup.db"
        source_conn = get_db_connection()
        backup_conn = sqlite3.connect(backup_path)
        with backup_conn:
            source_conn.backup(backup_conn)
        source_conn.close()
        backup_conn.close()
        return True, "Backup successful!"
    except sqlite3.Error as e:
        logger.error(f"Database backup failed: {e}")
        return False, "Database backup failed. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        return False, "An unexpected error occurred during backup."
            
def restore_database():
    """Restores the database from a backup file."""
    conn = None
    try:
        backup_path = "/data/wonderful_wino_backup.db"
        if not os.path.exists(backup_path):
            return False, "Backup file not found."
        
        source_conn = sqlite3.connect(backup_path)
        dest_conn = get_db_connection()
        with dest_conn:
            source_conn.backup(dest_conn)
        source_conn.close()
        dest_conn.close()
        return True, "Database restored successfully. The page will now refresh."
    except sqlite3.Error as e:
        logger.error(f"Database restore failed: {e}")
        return False, "Database restore failed. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error during restore: {e}")
        return False, "An unexpected error occurred during restore."

def get_settings():
    """Retrieves all settings from the database."""
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
        if conn: conn.close()

def save_settings(data: dict):
    """Saves or updates settings in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for key, value in data.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error saving settings: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

# Note: The `os` import is needed for the backup/restore functions.
import os
