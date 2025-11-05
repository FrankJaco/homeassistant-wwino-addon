import sqlite3
import logging
from .config import DB_PATH
import os
from collections import defaultdict # For Home Assistant inventory counts

logger = logging.getLogger(__name__)

# --- SECURITY FIX: Whitelist of allowed column names for updates ---
# These are the only columns in the 'wines' table that are allowed to be updated
# via the update_wine_details function. This prevents SQL injection by
# ensuring keys from user-controlled 'updates' dict cannot inject malicious SQL.
ALLOWED_WINE_UPDATE_COLUMNS = {
    'name', 'vintage', 'varietal', 'region', 'country', 'region_full',
    'vivino_rating', 'image_url', 'cost_tier', 'personal_rating',
    'tasting_notes', 'alcohol_percent', 'wine_type', 'needs_review',
    'image_focal_point', 'image_zoom'
}

def get_db_connection():
    """Establishes and returns a database connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables and performs schema migrations if necessary."""
    conn = None
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = get_db_connection()
        cursor = conn.cursor()

        # --- Base Table Creation ---
        
        # Wines Table: Stores the details of each unique wine
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
                image_zoom REAL DEFAULT 1
            )
        ''')

        # Settings Table (Restored)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Inventory History Table: Logs all changes (ADD, CONSUME, REVIEW, DELETE)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wine_id INTEGER NOT NULL,
                change_type TEXT NOT NULL, -- 'ADD', 'CONSUME', 'REVIEW', 'DELETE'
                quantity_change INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wine_id) REFERENCES wines (id)
            )
        ''')

        # --- SCHEMA MIGRATION LOGIC (RESTORED) ---

        # Check wines table columns
        cursor.execute("PRAGMA table_info(wines)")
        wines_columns = [col[1] for col in cursor.fetchall()]

        if 'alcohol_percent' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN alcohol_percent REAL")
            logger.info("Migrated wines table: Added alcohol_percent column.")
        
        if 'wine_type' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN wine_type TEXT")
            logger.info("Migrated wines table: Added wine_type column.")
            
        if 'image_focal_point' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN image_focal_point TEXT DEFAULT '50%'")
            logger.info("Migrated wines table: Added image_focal_point column.")

        if 'image_zoom' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN image_zoom REAL DEFAULT 1")
            logger.info("Migrated wines table: Added image_zoom column.")

        if 'needs_review' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN needs_review BOOLEAN DEFAULT FALSE")
            logger.info("Migrated wines table: Added needs_review column.")

        if 'added_at' not in wines_columns:
            cursor.execute("ALTER TABLE wines ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logger.info("Migrated wines table: Added added_at column.")
        
        # Check history table columns for older, non-standard names and replace/adjust if necessary
        # The history table name changed from 'consumption_history' to 'inventory_history' for robustness
        # If the old table exists, the app will continue to use the new one, but we don't attempt to migrate data
        # between them here for safety, just ensuring the new, critical columns exist on wines.

        conn.commit()
        logger.info(f"Database initialized successfully at {DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

def reinitialize_database():
    """Drops all existing tables and re-initializes the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.warning("Dropping all database tables for re-initialization.")
        cursor.execute("DROP TABLE IF EXISTS wines")
        cursor.execute("DROP TABLE IF EXISTS settings")
        cursor.execute("DROP TABLE IF EXISTS inventory_history")
        conn.commit()
        init_db()
        logger.info("Database successfully re-initialized.")
    except sqlite3.Error as e:
        logger.error(f"Database re-initialization error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# --- CRUD and Core Functions ---

def add_wine(vivino_url, name, vintage, varietal, region, country, region_full, vivino_rating, image_url, alcohol_percent, wine_type, quantity, needs_review):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if wine already exists by vivino_url
        cursor.execute("SELECT id, quantity FROM wines WHERE vivino_url = ?", (vivino_url,))
        existing_wine = cursor.fetchone()

        if existing_wine:
            # Wine exists, increment quantity
            wine_id = existing_wine['id']
            new_quantity = existing_wine['quantity'] + quantity
            cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine_id))
            conn.commit()
            logger.info(f"Updated quantity for existing wine ID {wine_id} to {new_quantity}.")
            # Log the change
            log_inventory_change(wine_id, 'ADD', quantity)
            return wine_id
        else:
            # New wine, insert it
            cursor.execute('''
                INSERT INTO wines (
                    vivino_url, name, vintage, varietal, region, country, region_full,
                    vivino_rating, image_url, alcohol_percent, wine_type, quantity, needs_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                vivino_url, name, vintage, varietal, region, country, region_full,
                vivino_rating, image_url, alcohol_percent, wine_type, quantity, needs_review
            ))
            conn.commit()
            wine_id = cursor.lastrowid
            logger.info(f"Added new wine ID {wine_id}: {name} ({vintage}).")
            # Log the change
            log_inventory_change(wine_id, 'ADD', quantity)
            return wine_id

    except sqlite3.IntegrityError:
        logger.warning(f"Attempted to add duplicate Vivino URL: {vivino_url}. Handled by update logic.")
        return None 
    except sqlite3.Error as e:
        logger.error(f"Database error adding wine: {e}")
        return None
    finally:
        if conn: conn.close()

def get_wine_by_id(wine_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
        wine = cursor.fetchone()
        return dict(wine) if wine else None
    except sqlite3.Error as e:
        logger.error(f"Database error getting wine by ID: {e}")
        return None
    finally:
        if conn: conn.close()

def get_wine_by_url(vivino_url):
    """Fetches a wine by its Vivino URL."""
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
        if conn: conn.close()

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

def get_all_wines(status_filter='on_hand', sort_by='name'):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM wines"

        # Apply filter based on status
        if status_filter == 'on_hand':
            query += " WHERE quantity > 0"
        elif status_filter == 'needs_review':
            query += " WHERE needs_review = TRUE AND quantity > 0"
        elif status_filter == 'consumed':
            query += " WHERE quantity = 0"
        # 'all' filter needs no WHERE clause

        # Apply sorting
        if sort_by == 'rating':
            # Order by personal_rating (non-null first), then vivino_rating
            query += " ORDER BY personal_rating IS NULL, personal_rating DESC, vivino_rating IS NULL, vivino_rating DESC, name ASC"
        elif sort_by == 'vintage':
            query += " ORDER BY vintage DESC, name ASC"
        elif sort_by == 'added_at':
            query += " ORDER BY added_at DESC"
        elif sort_by == 'name':
            query += " ORDER BY name COLLATE NOCASE ASC"
        else:
            query += " ORDER BY name COLLATE NOCASE ASC"

        cursor.execute(query)
        wines = cursor.fetchall()
        return [dict(wine) for wine in wines]
    except sqlite3.Error as e:
        logger.error(f"Database error getting all wines: {e}")
        return []
    finally:
        if conn: conn.close()

def get_all_historical_wines():
    """
    Returns ALL wines ever added (including those with quantity=0),
    used primarily for HA list cleanup during force-clear/restore.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Note: We select all records from 'wines' table, regardless of quantity.
        query = "SELECT * FROM wines"
        cursor.execute(query)
        wines = cursor.fetchall()
        return [dict(wine) for wine in wines]
    except sqlite3.Error as e:
        logger.error(f"Database error getting all historical wines: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_wine_details(wine_id, updates):
    """
    Updates general details for a wine by ID. Used for notes, rating, focal point, etc.
    Updates is a dict of {column_name: new_value}.
    
    SECURITY FIX: Filters updates against a whitelist of allowed columns.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Filter the updates dictionary against the security whitelist
        safe_updates = {
            k: v for k, v in updates.items() 
            if k in ALLOWED_WINE_UPDATE_COLUMNS
        }
        
        if not safe_updates:
            logger.warning(f"No valid update columns provided for wine ID {wine_id}. Updates tried: {updates.keys()}")
            return True # Nothing valid to update, still considered successful

        # Build the SET part of the query dynamically using ONLY the safe keys
        set_clauses = [f"{key} = ?" for key in safe_updates.keys()]
        query = f"UPDATE wines SET {', '.join(set_clauses)} WHERE id = ?"
        values = list(safe_updates.values()) + [wine_id]

        cursor.execute(query, values)
        conn.commit()
        logger.info(f"Updated wine ID {wine_id} details: {safe_updates.keys()}")

        # Log history if the personal rating was updated
        if 'personal_rating' in updates and updates['personal_rating'] is not None:
             log_inventory_change(wine_id, 'REVIEW', 0)

        return True
    except sqlite3.Error as e:
        logger.error(f"Database error updating wine ID {wine_id}: {e}")
        return False
    finally:
        if conn: conn.close()

def delete_wine_by_id(wine_id):
    """'Soft-deletes' a wine by setting its quantity to 0."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current quantity for logging
        cursor.execute("SELECT quantity FROM wines WHERE id = ?", (wine_id,))
        wine = cursor.fetchone()
        if not wine:
            logger.warning(f"Attempted to delete non-existent wine ID {wine_id}.")
            return False

        quantity_deleted = wine['quantity']

        # Set quantity to 0 and mark as not needing review
        cursor.execute("UPDATE wines SET quantity = 0, needs_review = FALSE WHERE id = ?", (wine_id,))

        # Log the change
        if quantity_deleted > 0:
            log_inventory_change(wine_id, 'DELETE', -quantity_deleted)

        conn.commit()
        logger.info(f"Soft-deleted/Consumed all bottles of wine ID {wine_id}. Quantity set to 0.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine ID {wine_id}: {e}")
        return False
    finally:
        if conn: conn.close()

# --- Settings Functions (Restored) ---

def get_settings():
    """Fetches all key-value pairs from the settings table."""
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
    """Updates or inserts multiple key-value pairs into the settings table."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for key, value in data.items():
            cursor.execute('''
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (key, value))
        conn.commit()
        logger.info(f"Updated settings for keys: {list(data.keys())}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error updating settings: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- Inventory History Functions ---

def log_inventory_change(wine_id, change_type, quantity_change):
    """Logs an inventory or review action."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO inventory_history (wine_id, change_type, quantity_change)
            VALUES (?, ?, ?)
        ''', (wine_id, change_type, quantity_change))
        conn.commit()
        logger.debug(f"Logged change: Wine ID {wine_id}, Type: {change_type}, Change: {quantity_change}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error logging inventory change: {e}")
        return False
    finally:
        if conn: conn.close()

def get_inventory_history(wine_id=None):
    """Fetches all history records, optionally filtered by wine_id."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                h.timestamp,
                h.change_type,
                h.quantity_change,
                w.name,
                w.vintage,
                w.wine_type,
                w.id as wine_id
            FROM inventory_history h
            JOIN wines w ON h.wine_id = w.id
        """
        params = []
        if wine_id is not None:
            query += " WHERE h.wine_id = ?"
            params.append(wine_id)

        query += " ORDER BY h.timestamp DESC"

        cursor.execute(query, params)
        history = cursor.fetchall()
        return [dict(item) for item in history]
    except sqlite3.Error as e:
        logger.error(f"Database error getting inventory history: {e}")
        return []
    finally:
        if conn: conn.close()


# --- HA Integration Support Functions ---

def get_inventory_counts():
    """
    Calculates and returns inventory summary counts needed for HA sensors.
    Returns: {'total_quantity': X, 'unique_wines': Y, 'Red': Z, 'White': A, ...}
    """
    conn = None
    counts = defaultdict(int)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total unique wines (count of rows with quantity > 0)
        cursor.execute("SELECT COUNT(id) FROM wines WHERE quantity > 0")
        counts['unique_wines'] = cursor.fetchone()[0]

        # Total bottle count
        cursor.execute("SELECT SUM(quantity) FROM wines")
        counts['total_quantity'] = cursor.fetchone()[0] or 0

        # Counts by wine_type
        cursor.execute("SELECT wine_type, SUM(quantity) FROM wines WHERE quantity > 0 GROUP BY wine_type")
        for row in cursor.fetchall():
            wine_type, qty = row
            if wine_type:
                counts[wine_type] = qty

        return dict(counts)
    except sqlite3.Error as e:
        logger.error(f"Database error getting inventory counts: {e}")
        return dict(counts)
    finally:
        if conn: conn.close()

def get_wines_needing_review_count():
    """Returns the count of wines (not bottles) that are marked needs_review and are currently in stock."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Count wines where the 'needs_review' flag is true AND quantity is greater than 0
        cursor.execute("SELECT COUNT(id) FROM wines WHERE needs_review = TRUE AND quantity > 0")
        return cursor.fetchone()[0]
    except sqlite3.Error as e:
        logger.error(f"Database error getting review count: {e}")
        return 0
    finally:
        if conn: conn.close()

# --- Backup and Restore Functions ---

def backup_database():
    """Creates a backup of the current database to a .bak file."""
    backup_path = f"{DB_PATH}.bak"
    conn = None
    backup_conn = None
    try:
        # 1. Connect to the source database
        conn = get_db_connection()
        # 2. Connect to the backup destination (will create the file)
        backup_conn = sqlite3.connect(backup_path)

        # 3. Use the SQLite built-in backup API
        conn.backup(backup_conn)

        logger.info(f"Database backed up successfully to {backup_path}")
        return True, f"Database backed up successfully to {backup_path}."
    except sqlite3.Error as e:
        logger.error(f"Database backup failed: {e}")
        return False, "Database backup failed."
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        return False, "An unexpected error occurred during backup."
    finally:
        if conn: conn.close()
        if backup_conn: backup_conn.close()

def restore_database():
    """Restores the database from the latest .bak file."""
    backup_path = f"{DB_PATH}.bak"
    if not os.path.exists(backup_path):
        return False, "No backup file found to restore."

    conn = None
    backup_conn = None
    try:
        # 1. Connect to the source backup file
        backup_conn = sqlite3.connect(backup_path)
        # 2. Connect to the destination file
        conn = get_db_connection()

        # 3. Use the SQLite built-in backup API to restore
        backup_conn.backup(conn)

        logger.warning(f"Database restored successfully from {backup_path}")
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