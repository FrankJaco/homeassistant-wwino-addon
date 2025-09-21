import sqlite3
import logging
import os
from .config import DB_PATH

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes and returns a database connection with Row factory."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection failed: {e}")
        return None

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = get_db_connection()
    if not conn:
        return

    try:
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
    """Drops all tables and recreates them for a clean start."""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        logger.warning("Dropping existing 'wines' and 'settings' tables.")
        cursor.execute("DROP TABLE IF EXISTS wines")
        cursor.execute("DROP TABLE IF EXISTS settings")
        conn.commit()
        logger.info("Successfully dropped tables.")
        # Call init_db to recreate them
        init_db()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database reinitialization failed: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_settings():
    """Retrieves all settings from the database as a dictionary."""
    conn = get_db_connection()
    if not conn:
        return {}

    try:
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

def update_settings(settings_data: dict):
    """Saves or updates settings in the database."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        for key, value in settings_data.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error updating settings: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_wine_by_url(vivino_url: str):
    """Fetches a single wine by its Vivino URL."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine = cursor.fetchone()
        return dict(wine) if wine else None
    finally:
        if conn: conn.close()
        
def get_wine_by_name_and_vintage(name: str, vintage: int):
    """Fetches a single wine by its name and vintage."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        if vintage is not None:
            cursor.execute("SELECT * FROM wines WHERE LOWER(name) = LOWER(?) AND vintage = ?", (name, vintage))
        else:
            cursor.execute("SELECT * FROM wines WHERE LOWER(name) = LOWER(?) AND vintage IS NULL", (name,))
        wine = cursor.fetchone()
        return dict(wine) if wine else None
    finally:
        if conn: conn.close()

def add_or_update_wine(wine_data: dict, quantity: int, cost_tier: int):
    """Inserts a new wine or updates the quantity of an existing one."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        # Check if a wine with the same name and vintage already exists to decide canonical URL
        existing_by_name = get_wine_by_name_and_vintage(wine_data['name'], wine_data['vintage'])
        
        vivino_url_to_use = existing_by_name['vivino_url'] if existing_by_name else wine_data['vivino_url']
        wine_data['vivino_url'] = vivino_url_to_use # Standardize the URL

        existing_wine = get_wine_by_url(vivino_url_to_use)

        if existing_wine:
            new_quantity = existing_wine['quantity'] + quantity
            cursor.execute('''
                UPDATE wines SET quantity = ?, name = ?, vintage = ?, varietal = ?, region = ?,
                country = ?, vivino_rating = ?, image_url = ?, cost_tier = ?, added_at = CURRENT_TIMESTAMP
                WHERE vivino_url = ?
            ''', (
                new_quantity, wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                wine_data['image_url'], cost_tier, vivino_url_to_use
            ))
            logger.info(f"Updated quantity for '{wine_data['name']}' to {new_quantity}.")
        else:
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, image_url, quantity, cost_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wine_data['vivino_url'], wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                wine_data['image_url'], quantity, cost_tier
            ))
            logger.info(f"New wine '{wine_data['name']}' inserted with quantity {quantity}.")
        conn.commit()
        return get_wine_by_url(vivino_url_to_use) # Return the full, updated record
    except sqlite3.Error as e:
        logger.error(f"Database error inserting/updating wine: {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def edit_wine(vivino_url: str, update_data: dict):
    """Updates the details of a specific wine."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, 
            quantity = ?, cost_tier = ?, personal_rating = ?, tasting_notes = ? WHERE vivino_url = ?
        ''', (
            update_data['name'], update_data['vintage'], update_data.get('varietal', "Unknown Varietal"),
            update_data.get('region', "Unknown Region"), update_data.get('country', "Unknown Country"),
            update_data['quantity'], update_data.get('cost_tier'), update_data.get('personal_rating'),
            update_data.get('tasting_notes'), vivino_url
        ))
        conn.commit()
        return get_wine_by_url(vivino_url)
    except sqlite3.Error as e:
        logger.error(f"Database error editing wine: {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def get_inventory(status_filter: str = 'on_hand'):
    """Gets all wines from inventory based on a filter ('on_hand', 'history', or 'all')."""
    conn = get_db_connection()
    if not conn: return []
    
    query = "SELECT * FROM wines"
    if status_filter == 'on_hand':
        query += " WHERE quantity > 0"
    elif status_filter == 'history':
        query += " WHERE quantity = 0"
    query += " ORDER BY added_at DESC"
    
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        wines = cursor.fetchall()
        return [dict(wine) for wine in wines]
    except sqlite3.Error as e:
        logger.error(f"Database error fetching inventory: {e}")
        return []
    finally:
        if conn: conn.close()

def update_wine_quantity(vivino_url: str, quantity: int):
    """Sets the quantity for a specific wine."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (quantity, vivino_url))
        conn.commit()
        return get_wine_by_url(vivino_url)
    except sqlite3.Error as e:
        logger.error(f"Database error updating quantity: {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def consume_wine(wine_id: int, personal_rating: float = None):
    """Decrements a wine's quantity by 1 and optionally sets a personal rating."""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM wines WHERE id = ?", (wine_id,))
        result = cursor.fetchone()
        if not result or result['quantity'] <= 0:
            return None # Or return current state

        new_quantity = result['quantity'] - 1
        
        if personal_rating is not None:
            cursor.execute("UPDATE wines SET quantity = ?, personal_rating = ? WHERE id = ?", (new_quantity, personal_rating, wine_id))
        else:
            cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine_id))
        
        conn.commit()
        cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
        return dict(cursor.fetchone())
    except sqlite3.Error as e:
        logger.error(f"Database error consuming wine: {e}")
        conn.rollback()
        return None
    finally:
        if conn: conn.close()

def delete_wine(vivino_url: str):
    """Deletes a wine from the database entirely."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        return cursor.rowcount > 0 # Returns True if a row was deleted
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine: {e}")
        conn.rollback()
        return False
    finally:
        if conn: conn.close()

def rate_wine(vivino_url: str, rating: float):
    """Sets the personal rating for a specific wine."""
    return edit_wine(vivino_url, {'personal_rating': rating})

def save_wine_details(vivino_url: str, details: dict):
    """Saves tasting notes and/or a new image URL for a wine."""
    conn = get_db_connection()
    if not conn: return False

    updates = []
    params = []
    if 'tasting_notes' in details:
        updates.append("tasting_notes = ?")
        params.append(details['tasting_notes'])
    if 'image_url' in details:
        updates.append("image_url = ?")
        params.append(details['image_url'])

    if not updates: return True # No changes needed

    query = f"UPDATE wines SET {', '.join(updates)} WHERE vivino_url = ?"
    params.append(vivino_url)
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error saving details: {e}")
        conn.rollback()
        return False
    finally:
        if conn: conn.close()

def backup_database():
    """Creates a safe backup of the database to the /data directory."""
    backup_dir = os.path.dirname(DB_PATH)
    backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")
    logger.info(f"Starting database backup from {DB_PATH} to {backup_path}")
    
    source_conn = get_db_connection()
    if not source_conn: return False

    backup_conn = None
    try:
        backup_conn = sqlite3.connect(backup_path)
        with backup_conn:
            source_conn.backup(backup_conn)
        logger.info("Database backup completed successfully.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database backup failed: {e}")
        return False
    finally:
        if source_conn: source_conn.close()
        if backup_conn: backup_conn.close()

def restore_database():
    """Restores the database from the backup file."""
    backup_dir = os.path.dirname(DB_PATH)
    backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")

    if not os.path.exists(backup_path):
        logger.warning(f"Restore failed: Backup file not found at {backup_path}")
        return False

    logger.info(f"Starting database restore from {backup_path} to {DB_PATH}")
    
    dest_conn = get_db_connection()
    if not dest_conn: return False
    
    source_conn = None
    try:
        source_conn = sqlite3.connect(backup_path)
        with dest_conn:
            source_conn.backup(dest_conn)
        logger.info("Database restore completed successfully.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database restore failed: {e}")
        return False
    finally:
        if dest_conn: dest_conn.close()
        if source_conn: source_conn.close()
