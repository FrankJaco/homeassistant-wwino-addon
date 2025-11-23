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
                region_full TEXT,
                vivino_rating REAL,
                image_url TEXT,
                quantity INTEGER DEFAULT 1,
                cost_tier INTEGER,
                personal_rating REAL,
                tasting_notes TEXT,
                alcohol_percent REAL,
                wine_type TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                needs_review BOOLEAN DEFAULT FALSE,
                image_focal_point TEXT DEFAULT '50%',
                image_zoom REAL DEFAULT 1,
                image_tilt REAL DEFAULT 0
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
                log_type TEXT DEFAULT 'consumed' NOT NULL,
                cost_tier INTEGER,
                FOREIGN KEY (wine_id) REFERENCES wines (id) ON DELETE CASCADE
            )
        ''')
        
        # Check if new columns exist in wines table and add them if they don't
        cursor.execute("PRAGMA table_info(wines)")
        wines_columns = [column['name'] for column in cursor.fetchall()]
        if 'alcohol_percent' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN alcohol_percent REAL")
            logger.info("Added 'alcohol_percent' column to wines table.")
        if 'wine_type' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN wine_type TEXT")
            logger.info("Added 'wine_type' column to wines table.")
        if 'image_focal_point' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN image_focal_point TEXT DEFAULT '50%'")
            logger.info("Added 'image_focal_point' column to wines table.")
        if 'image_zoom' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN image_zoom REAL DEFAULT 1")
            logger.info("Added 'image_zoom' column to wines table.")
        if 'image_tilt' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN image_tilt REAL DEFAULT 0")
            logger.info("Added 'image_tilt' column to wines table.")
        if 'region_full' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN region_full TEXT")
            logger.info("Added 'region_full' column to wines table.")

        # Check if new columns exist in consumption_history table and add them if they don't
        cursor.execute("PRAGMA table_info(consumption_history)")
        ch_columns = [column['name'] for column in cursor.fetchall()]
        if 'log_type' not in ch_columns:
            cursor.execute("ALTER TABLE consumption_history ADD COLUMN log_type TEXT DEFAULT 'consumed' NOT NULL")
            logger.info("Added 'log_type' column to consumption_history table.")
        if 'cost_tier' not in ch_columns:
            cursor.execute("ALTER TABLE consumption_history ADD COLUMN cost_tier INTEGER")
            logger.info("Added 'cost_tier' column to consumption_history table.")

        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()

# --- NEW FUNCTION ---
def update_consumption_date(log_id, new_consumed_at):
    """Updates the consumed_at timestamp for a specific log entry."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE consumption_history SET consumed_at = ? WHERE id = ?",
            (new_consumed_at, log_id)
        )
        conn.commit()
        logger.info(f"Updated consumed_at for log_id: {log_id}")
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating log date: {e}")
        if conn:
            conn.rollback()
        return False
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

def update_image_focal_point(vivino_url: str, focal_point: str):
    """Updates the image focal point for a specific wine."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE wines SET image_focal_point = ? WHERE vivino_url = ?",
            (focal_point, vivino_url)
        )
        conn.commit()
        logger.info(f"Updated focal point for {vivino_url} to {focal_point}")
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error updating focal point: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def add_consumption_record(cursor, wine_id, personal_rating, cost_tier):
    """
    Adds a new record to the consumption_history table.
    NOTE: This function is designed to be called within an existing transaction
    by passing an active cursor.
    """
    cursor.execute(
        "INSERT INTO consumption_history (wine_id, personal_rating, log_type, cost_tier) VALUES (?, ?, 'consumed', ?)",
        (wine_id, personal_rating, cost_tier)
    )
    logger.info(f"Added consumption record for wine_id: {wine_id}")


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

def add_or_update_wine(wine_data: dict, quantity: int, cost_tier: int):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, quantity FROM wines WHERE vivino_url = ?", (wine_data['vivino_url'],))
        existing_wine = cursor.fetchone()

        needs_review_flag = wine_data.get('needs_review', False) or \
                            wine_data.get('name', '').startswith(('Review Wine', 'Vivino Wine ID'))

        if existing_wine:
            wine_id, current_quantity = existing_wine
            new_quantity = current_quantity + quantity
            try:
                cursor.execute('''
                    INSERT INTO consumption_history (wine_id, log_type, cost_tier)
                    VALUES (?, 'acquired', ?)
                ''', (wine_id, cost_tier))
                logger.info(f"Logged 'acquired' event for existing wine_id: {wine_id}")
            except sqlite3.Error as e:
                # Log the error but don't stop the whole transaction
                logger.error(f"Failed to insert 'acquired' log for existing wine: {e}")
            if needs_review_flag:
                cursor.execute('UPDATE wines SET quantity = ? WHERE id = ?', (new_quantity, wine_id))
                logger.info(f"Updated quantity only for '{wine_data['name']}' to {new_quantity} as it needs review.")
            else:
                cursor.execute('''
                    UPDATE wines SET
                        quantity = ?, name = ?, vintage = ?, varietal = ?, region = ?, region_full = ?,
                        country = ?, vivino_rating = ?, image_url = ?, cost_tier = ?,
                        alcohol_percent = ?, wine_type = ?, needs_review = ?
                    WHERE id = ?
                ''', (
                    new_quantity, wine_data.get('name'), wine_data.get('vintage'), wine_data.get('varietal'),
                    wine_data.get('region'), wine_data.get('region_full'), wine_data.get('country'), wine_data.get('vivino_rating'),
                    wine_data.get('image_url'), cost_tier, wine_data.get('alcohol_percent'),
                    wine_data.get('wine_type'), False, wine_id
                ))
                logger.info(f"Updated and refreshed data for '{wine_data.get('name')}' with new quantity {new_quantity}.")
        else:
            cursor.execute('''
                INSERT INTO wines (
                    vivino_url, name, vintage, varietal, region, region_full, country, vivino_rating,
                    image_url, quantity, cost_tier, personal_rating, tasting_notes,
                    alcohol_percent, wine_type, needs_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wine_data.get('vivino_url'), wine_data.get('name'), wine_data.get('vintage'), wine_data.get('varietal'),
                wine_data.get('region'), wine_data.get('region_full'), wine_data.get('country'), wine_data.get('vivino_rating'),
                wine_data.get('image_url'), quantity, cost_tier, None, None,
                wine_data.get('alcohol_percent'), wine_data.get('wine_type'), needs_review_flag
            ))
            new_wine_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO consumption_history (wine_id, log_type, cost_tier)
                VALUES (?, 'acquired', ?)
            ''', (new_wine_id, cost_tier))
            logger.info(f"New wine '{wine_data.get('name')}' inserted with quantity {quantity} and logged 'acquired' event.")

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

def update_wine_details(vivino_url, name, vintage, quantity, varietal, region, country, cost_tier, personal_rating, tasting_notes, alcohol_percent, wine_type):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?,
            quantity = ?, cost_tier = ?, personal_rating = ?, tasting_notes = ?,
            alcohol_percent = ?, wine_type = ?, needs_review = FALSE
            WHERE vivino_url = ?
        ''', (name, vintage, varietal, region, country, quantity, cost_tier, personal_rating, tasting_notes, alcohol_percent, wine_type, vivino_url))
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

def update_wine_notes_and_image(vivino_url, notes, image_url, image_zoom, image_tilt):
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
        if image_zoom is not None:
            updates.append("image_zoom = ?")
            params.append(image_zoom)
        if image_tilt is not None:
            updates.append("image_tilt = ?")
            params.append(image_tilt)

        if updates:
            # This query is still safe as the *structure* is built from
            # fixed strings, not user input. The user input is only
            # in the params list.
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

def atomically_consume_wine(vivino_url, personal_rating):
    """
    Atomically decrements wine quantity and logs consumption in a transaction.
    This prevents race conditions.
    """
    conn = None
    try:
        conn = get_db_connection()
        conn.isolation_level = 'EXCLUSIVE' # Lock the database for this transaction
        cursor = conn.cursor()
        cursor.execute("BEGIN EXCLUSIVE TRANSACTION")

        # Step 1: Get the current wine state
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine = cursor.fetchone()
        
        if not wine:
            conn.rollback()
            return ("error", "Wine not found", None)
        
        wine_dict = dict(wine)
        current_quantity = wine_dict.get('quantity', 0)
        
        if current_quantity <= 0:
            conn.rollback()
            return ("error", "Quantity already zero", None)

        # Step 2: Calculate new state
        new_quantity = current_quantity - 1
        rating_to_set = personal_rating if personal_rating is not None else wine_dict.get('personal_rating')

        # Step 3: Update the wine record
        cursor.execute(
            "UPDATE wines SET quantity = ?, personal_rating = ? WHERE vivino_url = ?",
            (new_quantity, rating_to_set, vivino_url)
        )
        
        # Step 4: Add the consumption log record
        wine_id = wine_dict['id']
        cost_tier = wine_dict.get('cost_tier')
        add_consumption_record(cursor, wine_id, personal_rating, cost_tier)

        # Step 5: Commit the transaction
        conn.commit()

        updated_wine = get_wine_by_url(vivino_url)
        return ("success", new_quantity, updated_wine)

    except sqlite3.Error as e:
        logger.error(f"Database error during atomic consume: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return ("error", "Database error", None)
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

# --- NEW FUNCTION FOR HA SENSORS ---
def get_inventory_statistics():
    """
    Calculates inventory statistics using a single, safe SQL query.
    This is 100% CodeQL-safe as the query is a fixed literal.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                SUM(CASE WHEN quantity > 0 THEN quantity ELSE 0 END) as total_bottles,
                SUM(CASE WHEN wine_type = 'Red' AND quantity > 0 THEN quantity ELSE 0 END) as red_bottles,
                SUM(CASE WHEN wine_type = 'White' AND quantity > 0 THEN quantity ELSE 0 END) as white_bottles,
                SUM(CASE WHEN wine_type = 'Sparkling' AND quantity > 0 THEN quantity ELSE 0 END) as sparkling_bottles,
                SUM(CASE WHEN wine_type = 'Rosé' AND quantity > 0 THEN quantity ELSE 0 END) as rose_bottles,
                SUM(CASE WHEN wine_type = 'Dessert' AND quantity > 0 THEN quantity ELSE 0 END) as dessert_bottles,
                
                COUNT(CASE WHEN quantity > 0 THEN 1 END) as unique_wines,
                COUNT(CASE WHEN wine_type = 'Red' AND quantity > 0 THEN 1 END) as unique_red_wines,
                COUNT(CASE WHEN wine_type = 'White' AND quantity > 0 THEN 1 END) as unique_white_wines,
                COUNT(CASE WHEN wine_type = 'Sparkling' AND quantity > 0 THEN 1 END) as unique_sparkling_wines,
                COUNT(CASE WHEN wine_type = 'Rosé' AND quantity > 0 THEN 1 END) as unique_rose_wines,
                COUNT(CASE WHEN wine_type = 'Dessert' AND quantity > 0 THEN 1 END) as unique_dessert_wines,

                COUNT(CASE WHEN needs_review = TRUE AND quantity > 0 THEN 1 END) as needs_review
            FROM wines
        """
        cursor.execute(query)
        stats = cursor.fetchone()
        
        if stats:
            # Convert row object to dict and handle None (from SUM on no rows)
            stats_dict = dict(stats)
            for key in stats_dict:
                if stats_dict[key] is None:
                    stats_dict[key] = 0
            return stats_dict
        else:
            # Return a zeroed-out dict if the table is empty
            return {
                'total_bottles': 0, 'red_bottles': 0, 'white_bottles': 0,
                'sparkling_bottles': 0, 'rose_bottles': 0, 'dessert_bottles': 0,
                'unique_wines': 0, 'unique_red_wines': 0, 'unique_white_wines': 0,
                'unique_sparkling_wines': 0, 'unique_rose_wines': 0, 'unique_dessert_wines': 0,
                'needs_review': 0
            }
            
    except sqlite3.Error as e:
        logger.error(f"Database error getting inventory statistics: {e}")
        # Return a default structure on error
        return {
            'total_bottles': 0, 'red_bottles': 0, 'white_bottles': 0,
            'sparkling_bottles': 0, 'rose_bottles': 0, 'dessert_bottles': 0,
            'unique_wines': 0, 'unique_red_wines': 0, 'unique_white_wines': 0,
            'unique_sparkling_wines': 0, 'unique_rose_wines': 0, 'unique_dessert_wines': 0,
            'needs_review': 0
        }
    finally:
        if conn:
            conn.close()