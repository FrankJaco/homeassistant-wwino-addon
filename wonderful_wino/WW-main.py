import os
import logging
from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import requests
from bs4 import BeautifulSoup
import re # For regular expressions to clean strings
import json # For parsing JSON-LD data from Vivino
from flask_cors import CORS # Re-enabled CORS
from urllib.parse import urlparse, parse_qs
import time # For generating unique IDs for manual entries
import shutil
from vivino_scraper import scrape_vivino_data

# --- Configuration (read from environment variables) ---
HOME_ASSISTANT_URL = os.environ.get("HOME_ASSISTANT_URL")
HA_LONG_LIVED_TOKEN = os.environ.get("HA_LONG_LIVED_TOKEN")
TODO_LIST_ENTITY_ID = os.environ.get("TODO_LIST_ENTITY_ID")
DB_PATH = os.environ.get("DB_PATH", "/share/wwino/wine_inventory.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) # Ensure /share/wwino exists
LOG_LEVEL = os.environ.get("LOG_LEVEL", "debug").upper() # Set to debug for consistent logging

# --- Logging Setup ---
logging.basicConfig(level=getattr(logging, LOG_LEVEL),
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app) # Re-enabled CORS initialization

# --- Flask WSGI Middleware for Home Assistant Ingress ---
# This class helps Flask understand that it's running behind a proxy
# (Home Assistant's ingress) and that its URLs should be prefixed.
class ReverseProxied:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Home Assistant's ingress typically sets X-Forwarded-Prefix
        script_name = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            # Adjust PATH_INFO to be relative to SCRIPT_NAME
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        # Also handle X-Forwarded-Proto for HTTPS
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

# Apply the middleware to your Flask app
app.wsgi_app = ReverseProxied(app.wsgi_app)


# Dictionary for common country abbreviations for display purposes
COUNTRY_ABBREVIATIONS = {
    "United States": "US",
    "Australia": "AU",
    "France": "FR",
    "New Zealand": "NZ",
    "Italy": "IT",
    "Spain": "ES",
    "Argentina": "AR",
    "Chile": "CL",
    "Germany": "DE",
    "Portugal": "PT",
    "South Africa": "ZA",
    "Canada": "CA",
    "United Kingdom": "UK",
    "Austria": "AT",
    "Greece": "GR",
    "Hungary": "HU",
    "Lebanon": "LB",
    "Mexico": "MX",
    "Moldova": "MD",
    "Romania": "RO",
    "Switzerland": "CH",
    "Turkey": "TR",
    "Uruguay": "UY",
}


def format_wine_for_todo(wine: dict) -> str:
    """
    Formats the wine name and vintage for display in the Home Assistant To-Do list item summary.
    This format is also used for matching items for removal/update.
    Example: "Wine Name (2020)"
    """
    name = wine.get("name") or "n/a"
    vintage = wine.get("vintage")

    if vintage:
        return f"{name} ({vintage})"
    else:
        return name # If vintage is missing

def build_markdown_description(wine: dict, current_quantity: int, is_for_todo: bool = True) -> str:
    """
    Builds a Markdown-formatted description for the wine, used in the To-Do list item's description
    or for full display in the frontend. Includes varietal, region, country, quantity, and rating.
    Applies truncation and formatting rules based on 'is_for_todo' flag.
    """
    description_parts = []

    # Line 1: Varietals (bold first, 32 char limit, 60% truncation for ToDo)
    varietal_str = wine.get("varietal")

    rendered_varietal_line_markdown = []
    current_visual_length = 0

    MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL = 32
    TRUNCATION_THRESHOLD_PERCENT = 0.60
    ELLIPSIS_LENGTH = 0  # Not used for visual length, but kept for context

    if varietal_str and varietal_str != "Unknown Varietal":
        individual_varietals = [v.strip() for v in varietal_str.split(',')]
        if individual_varietals:
            if is_for_todo:
                # Bold the first grape (truncate if needed)
                first_grape = individual_varietals[0]
                visual_len_first_grape = len(first_grape)

                if visual_len_first_grape <= MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL:
                    rendered_varietal_line_markdown.append(f"**{first_grape}**")
                    current_visual_length += visual_len_first_grape
                else:
                    chars_for_truncated_grape = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - ELLIPSIS_LENGTH
                    if chars_for_truncated_grape > 0:
                        truncated_grape = first_grape[:chars_for_truncated_grape]
                        rendered_varietal_line_markdown.append(f"**{truncated_grape}**")
                        current_visual_length += len(truncated_grape)

                # --- Handle subsequent grapes for ToDo truncation ---
                for i, grape in enumerate(individual_varietals[1:]):
                    if not rendered_varietal_line_markdown and i > 0:  # If first grape was too long, don't add more
                        break

                    separator_text = " " if i == 0 else ", "
                    visual_len_grape = len(grape)

                    remaining_line_space = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - current_visual_length

                    if remaining_line_space >= (len(separator_text) + visual_len_grape):
                        rendered_varietal_line_markdown.append(f"{separator_text}{grape}")
                        current_visual_length += len(separator_text) + visual_len_grape
                    else:
                        space_for_grape_body = remaining_line_space - len(separator_text)

                        if space_for_grape_body > 0:
                            if (space_for_grape_body / visual_len_grape) >= TRUNCATION_THRESHOLD_PERCENT:
                                truncated_grape = grape[:space_for_grape_body]
                                rendered_varietal_line_markdown.append(f"{separator_text}{truncated_grape}")
                                current_visual_length += len(separator_text) + len(truncated_grape)
                        break
            else:
                # Full display: bold first, then list all
                rendered_varietal_line_markdown.append(f"**{individual_varietals[0]}**")
                if len(individual_varietals) > 1:
                    rendered_varietal_line_markdown.append(f", {', '.join(individual_varietals[1:])}")

    description_parts.append("".join(rendered_varietal_line_markdown) if rendered_varietal_line_markdown else "Unknown Varietal")

    # Line 2: Region + Country (with truncation for ToDo)
    region_str = wine.get("region")
    country_str = wine.get("country")

    region_country_display = []
    current_rc_visual_length = 0

    if region_str and region_str != "Unknown Region":
        if is_for_todo:
            # Bold region (truncate if needed)
            visual_len_region = len(region_str)
            if visual_len_region <= MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL:
                region_country_display.append(f"**{region_str}**")
                current_rc_visual_length += visual_len_region
            else:
                chars_for_truncated_region = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - ELLIPSIS_LENGTH
                if chars_for_truncated_region > 0:
                    truncated_region = region_str[:chars_for_truncated_region]
                    region_country_display.append(f"**{truncated_region}**")
                    current_rc_visual_length += len(truncated_region)
        else:
            region_country_display.append(f"**{region_str}**")

    if country_str and country_str != "Unknown Country":
        if is_for_todo:
            # Add country only if it fits
            if region_country_display:
                separator_rc = " "
            else:
                separator_rc = ""

            remaining_space_rc = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - current_rc_visual_length
            visual_len_country = len(country_str)

            if remaining_space_rc >= (len(separator_rc) + visual_len_country):
                region_country_display.append(f"{separator_rc}{country_str}")
                current_rc_visual_length += len(separator_rc) + visual_len_country
            else:
                space_for_country_body = remaining_space_rc - len(separator_rc)
                if space_for_country_body > 0 and (space_for_country_body / visual_len_country) >= TRUNCATION_THRESHOLD_PERCENT:
                    truncated_country = country_str[:space_for_country_body]
                    region_country_display.append(f"{separator_rc}{truncated_country}")
                # If no space for "X", then country won't be added to this line.
        else:
            # For full display, just add full country name
            region_country_display.append(f"{separator_rc}{country_str}")

    if region_country_display:
        description_parts.append("".join(region_country_display))
    else:
        description_parts.append("Unknown Region/Country")

    # --- Line 4: Qty, Ratings, B4B, and Cost Tier (formatted for markdown) ---
    # Rating logic (Vivino and/or personal)
    vivino_rating = wine.get('vivino_rating')
    personal_rating = wine.get('personal_rating')  # May be None
    display_rating = vivino_rating
    if personal_rating is not None and vivino_rating is not None:
        display_rating = (personal_rating + vivino_rating) / 2
    elif personal_rating is not None:
        display_rating = personal_rating

    # Cost tier (int -> '$' repeated)
    cost_tier = wine.get('cost_tier')

    # Prefer precomputed b4b_score from inventory; compute if absent and inputs available
    b4b_score = wine.get('b4b_score')
    if b4b_score is None and display_rating is not None and cost_tier is not None and isinstance(cost_tier, int) and cost_tier > 0:
        raw_score = (23.76 * display_rating) - (19.8 * cost_tier)
        b4b_score = round(raw_score, 1)

    # Build the markdown line in the requested order/style
    line4 = f"Qty: [ **{current_quantity}** ]"
    if display_rating is not None:
        line4 += f"&emsp;⭐**{display_rating:.1f}**"
    # Insert B4B score if available
    if b4b_score is not None:
        try:
            b4b_value = round(float(b4b_score))
            if b4b_value > 0:
                score_str = f"\u200B+{b4b_value}"  # zero-width space before plus
            else:
                score_str = str(b4b_value)
            if score_str.startswith("-"):
                score_str = "\u200B" + score_str  # zero-width space before minus
            line4 += f" | 🎯&nbsp;**{score_str}**"
        except Exception as e:
            logger.warning(f"Error formatting B4B score: {e}")
    if cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        cost_display = ''.join(['$'] * cost_tier)
        line4 += f" | **{cost_display}**"

    description_parts.append(line4)

    # Join the main parts with two spaces and a newline for proper Markdown line breaks
    # For ToDo, ensure we only join up to the first 3 elements
    if is_for_todo:
        return "  \n".join(description_parts[:3])
    else:
        # If not for ToDo, return all parts generated by this function (which is 3 lines)
        # The frontend will now construct its display from individual fields directly.
        return "  \n".join(description_parts)

# --- Database Initialization ---
def init_db():
    """Initializes the SQLite database, creating the 'wines' table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # MODIFICATION: Added tasting_notes column
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
    conn.close()
    logger.info(f"SQLite database initialized at {DB_PATH}")

def reinitialize_database():
    """
    Drops all existing tables and then recreates them by calling init_db().
    Useful for a clean start of the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        logger.warning("Attempting to reinitialize the database: Dropping existing 'wines' table.")
        cursor.execute("DROP TABLE IF EXISTS wines")
        cursor.execute("DROP TABLE IF EXISTS settings")
        conn.commit()
        logger.info("Successfully dropped 'wines' table (if it existed).")

        # Call your existing database initialization function to recreate tables
        init_db()
        logger.info("Successfully re-created database tables using init_db().")

    except sqlite3.Error as e:
        logger.error(f"Database error during reinitialization: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def sync_to_ha_todo(wine: dict, current_quantity: int) -> None:
    """
    Synchronizes a single wine item with the Home Assistant To-Do list.
    It first attempts to remove the item (in case of updates or deletion),
    then re-adds it if the quantity is greater than 0.
    """
    item_text = format_wine_for_todo(wine) # Formats as "Name (Vintage)"
    description = build_markdown_description(wine, current_quantity, is_for_todo=True) # Includes quantity in description
    entity_id = TODO_LIST_ENTITY_ID
    headers = {
        "Authorization": f"Bearer {HA_LONG_LIVED_TOKEN}",
        "Content-Type": "application/json",
    }
    # Create a redacted headers dictionary for logging to avoid exposing token
    redacted_headers = headers.copy()
    if "Authorization" in redacted_headers:
        redacted_headers["Authorization"] = "Bearer [REDACTED]"

    # Always attempt to remove the old item first to ensure updates are reflected
    remove_url = f"{HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    remove_payload = {
        "entity_id": entity_id,
        "item": item_text
    }
    logger.debug(f"HA To-Do remove_item request: URL={remove_url}, Headers={redacted_headers}, Payload={remove_payload}")
    try:
        resp = requests.post(remove_url, json=remove_payload, headers=headers, timeout=5)
        resp.raise_for_status()
        logger.info(f"HA To-Do removed (or attempted to remove) for update/deletion: {item_text}")
    except requests.exceptions.HTTPError as http_e:
        # Check for specific ServiceValidationError related to item not found
        if http_e.response.status_code == 500 and "Unable to find to-do list item" in http_e.response.text:
            logger.warning(
                f"HA To-Do remove attempt failed (Item Not Found) for '{item_text}'. "
                f"This can be ignored if adding a new wine for the first time or item was already removed. "
                f"Status: {http_e.response.status_code}, Response: {http_e.response.text}"
            )
        else:
            logger.error(
                f"HA To-Do remove attempt failed (HTTP Error) for '{item_text}'. "
                f"Status: {http_e.response.status_code}, Response: {http_e.response.text}"
            )
    except Exception as e:
        logger.warning(
            f"HA To-Do remove attempt failed for '{item_text}'. "
            f"This can be ignored if adding a new wine for the first time. "
            f"Check Home Assistant logs if this persists for existing items or indicates a network problem: {e}"
        )

    if current_quantity > 0:
        # If quantity > 0, re-add the item with the updated description
        add_url = f"{HOME_ASSISTANT_URL}/api/services/todo/add_item"
        add_payload = {
            "entity_id": entity_id,
            "item": item_text, # This now does NOT include quantity in the summary
            "description": description # This DOES include quantity in the detailed description
        }
        logger.debug(f"HA To-Do add_item request: URL={add_url}, Headers={redacted_headers}, Payload={add_payload}")
        try:
            resp = requests.post(add_url, json=add_payload, headers=headers, timeout=5)
            resp.raise_for_status()
            logger.info(f"HA To-Do synchronized (re-added/updated) for: {item_text} with quantity {current_quantity}")
        except requests.exceptions.HTTPError as http_e:
            logger.error(
                f"HA To-Do sync failed for add/update (HTTP Error): {item_text}. "
                f"Status: {http_e.response.status_code}, Response: {http_e.response.text}"
            )
        except Exception as e:
            logger.error(f"HA To-Do sync failed for add/update: {e}")
    else:
        logger.info(f"Wine quantity is 0. Item not re-added to HA To-Do: {item_text}")

def clear_ha_todo_list() -> None:
    """
    Attempts to clear all items from the configured Home Assistant To-Do list.
    Note: This function might be unreliable with some To-Do list integrations
    due to API limitations or the need for specific item UIDs for removal.
    It is currently commented out in the full sync process.
    """
    entity_id = TODO_LIST_ENTITY_ID
    headers = {
        "Authorization": f"Bearer {HA_LONG_LIVED_TOKEN}",
        "Content-Type": "application/json",
    }
    redacted_headers = headers.copy()
    if "Authorization" in redacted_headers:
        redacted_headers["Authorization"] = "Bearer [REDACTED]"

    clear_url = f"{HOME_ASSISTANT_URL}/api/services/todo/remove_all"
    payload = {
        "entity_id": entity_id
    }

    logger.debug(f"HA To-Do remove_all request: URL={clear_url}, Headers={redacted_headers}, Payload={payload}")
    resp = None
    try:
        resp = requests.post(clear_url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"Successfully sent request to clear all items from HA To-Do list: {entity_id}")
    except requests.exceptions.HTTPError as http_e:
        logger.error(
            f"Failed to clear all items from HA To-Do list '{entity_id}' (HTTP Error). "
            f"Status: {http_e.response.status_code}, Response: {http_e.response.text}"
        )
    except Exception as e:
        logger.error(
            f"Failed to clear all items from HA To-Do list '{entity_id}': {e}"
        )

def sync_db_to_ha_todo() -> None:
    """
    Performs a full synchronization of all wines from the local database
    to the Home Assistant To-Do list. It iterates through each wine and
    calls sync_to_ha_todo to ensure each item is correctly represented.
    """
    logger.info("Starting full synchronization from database to HA To-Do list.")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM wines")
        wines = cursor.fetchall()

        if not wines:
            logger.info("No wines found in database for synchronization. HA To-Do list will remain as is (unless database was just reinitialized).")
            return

        for wine in wines:
            wine_dict = dict(wine)
            sync_to_ha_todo(wine_dict, wine_dict.get('quantity', 0))

        logger.info(f"Completed synchronization of {len(wines)} wines from database to HA To-Do list.")
    except sqlite3.Error as e:
        logger.error(f"Database error during full sync to HA To-Do list: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during full sync to HA To-Do list: {e}")
    finally:
        if conn:
            conn.close()


def insert_wine_data(wine_data, quantity=1, cost_tier=None):
    """
    Inserts new wine data into the SQLite database or updates the quantity
    and other details if a wine with the same Vivino URL already exists.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
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
        else:
            # MODIFICATION: Added tasting_notes to insert statement
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
        logger.error(f"Database error inserting/updating wine data for {wine_data.get('name', 'N/A')}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Endpoint to retrieve all settings."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        settings_dict = {row['key']: row['value'] for row in rows}
        return jsonify(settings_dict), 200
    except sqlite3.Error as e:
        logger.error(f"Database error getting settings: {e}")
        return jsonify({"error": "Database error"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Endpoint to save or update settings."""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid data format"}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for key, value in data.items():
            # Use INSERT OR REPLACE to handle both new and existing keys
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        return jsonify({"status": "success", "message": "Settings updated successfully."}), 200
    except sqlite3.Error as e:
        logger.error(f"Database error updating settings: {e}")
        conn.rollback()
        return jsonify({"error": "Database error"}), 500
    finally:
        if conn:
            conn.close()

# --- Flask Routes ---

@app.route('/scan-wine', methods=['POST'])
def scan_wine():
    data = request.get_json()
    if not data or 'vivino_url' not in data:
        return jsonify({"status": "error", "message": "Missing 'vivino_url' in request body"}), 400

    vivino_url = data['vivino_url']
    quantity = data.get('quantity', 1)
    cost_tier = data.get('cost_tier')

    if not isinstance(quantity, int) or quantity < 1:
        quantity = 1

    wine_data = scrape_vivino_data(vivino_url)
    if not wine_data:
        return jsonify({"status": "error", "message": "Failed to scrape data from Vivino URL."}), 500

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM wines WHERE name = ? AND vintage IS ?", (wine_data['name'], wine_data['vintage']))
    existing_wine_row = cursor.fetchone()
    
    canonical_url_for_update = wine_data['vivino_url']

    if existing_wine_row:
        existing_wine_dict = dict(existing_wine_row)
        canonical_url_for_update = existing_wine_dict['vivino_url']
        wine_data['vivino_url'] = canonical_url_for_update

    conn.close()

    if insert_wine_data(wine_data, quantity, cost_tier):
        conn_post_insert = sqlite3.connect(DB_PATH)
        conn_post_insert.row_factory = sqlite3.Row 
        cursor_post_insert = conn_post_insert.cursor()
        cursor_post_insert.execute("SELECT * FROM wines WHERE vivino_url = ?", (canonical_url_for_update,))
        updated_wine_row = cursor_post_insert.fetchone()
        conn_post_insert.close()

        if updated_wine_row:
            updated_wine_dict = dict(updated_wine_row)
            current_total_quantity = updated_wine_dict.get('quantity', 0)
            sync_to_ha_todo(updated_wine_dict, current_total_quantity)
            return jsonify({
                "status": "success", "message": "Wine data scraped and stored/updated.",
                "wine_name": updated_wine_dict['name'], "vintage": updated_wine_dict['vintage'],
                "vivino_url": canonical_url_for_update, "quantity_added": quantity,
                "current_total_quantity": current_total_quantity
            }), 200
        else:
            return jsonify({"status": "error", "message": "Failed to retrieve wine after update."}), 500
    else:
        return jsonify({"status": "error", "message": "Failed to store/update wine data in database."}), 500

@app.route('/add-manual-wine', methods=['POST'])
def add_manual_wine():
    data = request.get_json()
    required_fields = ['name', 'vintage', 'quantity']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields (name, vintage, quantity)"}), 400

    quantity = data.get('quantity', 1)
    if not isinstance(quantity, int) or quantity < 1:
        quantity = 1
    cost_tier = data.get('cost_tier')
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', data['name'].replace(' ', '_')).lower()
    synthetic_url = f"manual:{safe_name}:{data['vintage']}"

    wine_data = {
        'vivino_url': synthetic_url, 'name': data['name'], 'vintage': data['vintage'],
        'varietal': data.get('varietal') or "Unknown Varietal",
        'region': data.get('region') or "Unknown Region",
        'country': data.get('country') or "Unknown Country",
        'vivino_rating': None,
        'image_url': data.get('image_url'),
        'cost_tier': None,
        'personal_rating': None,
    }

    if insert_wine_data(wine_data, quantity, cost_tier):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM wines WHERE vivino_url = ?", (synthetic_url,))
        current_total_quantity_row = cursor.fetchone()
        conn.close()
        current_total_quantity = current_total_quantity_row[0] if current_total_quantity_row else quantity
        sync_to_ha_todo(wine_data, current_total_quantity)
        return jsonify({
            "status": "success", "message": "Wine manually added/updated successfully.",
            "wine_name": wine_data['name'], "vintage": wine_data['vintage'],
            "vivino_url": wine_data['vivino_url'], "current_total_quantity": current_total_quantity
        }), 200
    else:
        return jsonify({"status": "error", "message": "Failed to store manual wine data in database."}), 500

@app.route('/edit-wine', methods=['POST'])
def edit_wine():
    data = request.get_json()
    required_fields = ['vivino_url', 'name', 'vintage', 'quantity']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields for editing."}), 400

    vivino_url = data['vivino_url']
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        old_wine_row = cursor.fetchone()
        if old_wine_row:
            old_wine_dict = dict(old_wine_row)
            sync_to_ha_todo(old_wine_dict, 0)
        else:
            return jsonify({"status": "error", "message": "Wine to edit not found."}), 404
        
        # MODIFICATION: Added tasting_notes to the update query
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, 
            quantity = ?, cost_tier = ?, personal_rating = ?, tasting_notes = ? WHERE vivino_url = ?
        ''', (
            data['name'], data['vintage'], data.get('varietal') or "Unknown Varietal",
            data.get('region') or "Unknown Region", data.get('country') or "Unknown Country",
            data['quantity'], data.get('cost_tier'), data.get('personal_rating'), 
            data.get('tasting_notes'), vivino_url
        ))
        conn.commit()

        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        updated_wine_row = cursor.fetchone()
        if updated_wine_row:
            updated_wine_dict = dict(updated_wine_row)
            sync_to_ha_todo(updated_wine_dict, updated_wine_dict['quantity'])

        return jsonify({"status": "success", "message": "Wine updated successfully."}), 200

    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error while editing wine."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/inventory', methods=['GET'])
def get_inventory():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    status_filter = request.args.get('filter', 'on_hand')
    query = "SELECT * FROM wines"
    conditions = []
    if status_filter == 'on_hand': conditions.append("quantity > 0")
    elif status_filter == 'history': conditions.append("quantity = 0")
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY added_at DESC"
    try:
        cursor.execute(query)
        wines = cursor.fetchall()

        # New logic to calculate B4B score
        wines_with_b4b = []
        for wine_row in wines:
            wine_dict = dict(wine_row)
            
            personal_rating = wine_dict.get('personal_rating')
            vivino_rating = wine_dict.get('vivino_rating')
            cost_tier = wine_dict.get('cost_tier')
            
            # Determine the hybrid display rating
            display_rating = None
            if personal_rating is not None and vivino_rating is not None:
                display_rating = (personal_rating + vivino_rating) / 2
            elif personal_rating is not None:
                display_rating = personal_rating
            elif vivino_rating is not None:
                display_rating = vivino_rating
            
            # Calculate B4B score if possible
            b4b_score = None
            try:
                if (
                    display_rating is not None
                    and isinstance(display_rating, (int, float))
                    and cost_tier is not None
                    and isinstance(cost_tier, int)
                    and cost_tier > 0
                ):
                    # Formula: (23.76 * Rating) - (19.8 * Cost Tier)
                    raw_score = (23.76 * display_rating) - (19.8 * cost_tier)
                    b4b_score = round(raw_score)  # Whole number
            except Exception as e:
                logger.warning(f"Skipping B4B calculation due to invalid data: {e}")
                b4b_score = None

            wine_dict['b4b_score'] = b4b_score
            wines_with_b4b.append(wine_dict)
            
        return jsonify(wines_with_b4b), 200
    finally:
        if conn: conn.close()

@app.route('/inventory/wine/set_quantity', methods=['POST'])
def set_wine_quantity():
    data = request.get_json()
    if not data or 'vivino_url' not in data or 'quantity' not in data:
        return jsonify({"status": "error", "message": "Missing 'vivino_url' or 'quantity'"}), 400
    vivino_url = data['vivino_url']
    new_quantity = data['quantity']
    if not isinstance(new_quantity, int) or new_quantity < 0:
        return jsonify({"status": "error", "message": "Quantity must be a non-negative integer."}), 400
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()
        if wine_data_row:
            columns = [description[0] for description in cursor.description]
            wine_data_dict = dict(zip(columns, wine_data_row))
            cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
            conn.commit()
            if cursor.rowcount > 0:
                sync_to_ha_todo(wine_data_dict, new_quantity)
                return jsonify({"status": "success", "message": f"Quantity set to {new_quantity}."}), 200
        return jsonify({"status": "error", "message": "Wine not found."}), 404
    finally:
        if conn: conn.close()

@app.route('/api/consume-wine', methods=['POST'])
def consume_wine_from_webhook():
    try:
        data = request.get_json()
        item_text = data.get("item")
        # NEW: Get the rating from the payload
        personal_rating = data.get("rating")
        
        if not item_text:
            logger.error("Webhook received without 'item' text.")
            return jsonify({"status": "error", "message": "Missing 'item' in request body"}), 400

        logger.info(f"Webhook received for consumed wine. Raw item_text: '{item_text}', Rating: {personal_rating}")

        parsed_name, parsed_vintage = None, None
        if item_text.endswith(')') and item_text[-6:-5] == '(' and item_text[-5:-1].isdigit() and len(item_text) > 6:
            try:
                parsed_vintage = int(item_text[-5:-1])
                parsed_name = item_text[:-6].rstrip()
            except (ValueError, IndexError):
                parsed_name = item_text.strip()
        else:
            parsed_name = item_text.strip()
        
        logger.info(f"Parsed name: '{parsed_name}', Parsed vintage: {parsed_vintage}")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
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
                    
                    # --- REPLACEMENT LOGIC ---
                    # Build the update query dynamically
                    update_query = "UPDATE wines SET quantity = ?"
                    update_params = [new_quantity]

                    if personal_rating is not None:
                        try:
                            # Validate that rating is a valid number
                            rating_val = float(personal_rating)
                            update_query += ", personal_rating = ?"
                            update_params.append(rating_val)
                            wine_data_dict['personal_rating'] = rating_val # Update for sync
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid rating value '{personal_rating}' received from webhook. Ignoring rating.")

                    update_query += " WHERE id = ?"
                    update_params.append(wine_data_dict['id'])
                    
                    cursor.execute(update_query, tuple(update_params))
                    # --- END REPLACEMENT ---

                    conn.commit()
                    logger.info(f"Decremented quantity for '{parsed_name} ({parsed_vintage or 'NV'})' to {new_quantity}")
                    
                    # Sync with the potentially updated rating
                    sync_to_ha_todo(wine_data_dict, new_quantity) 
                    
                    return jsonify({"status": "success", "message": f"Quantity updated. New quantity: {new_quantity}."}), 200
                else:
                    return jsonify({"status": "warning", "message": "Quantity already zero."}), 404
            return jsonify({"status": "warning", "message": "No matching wine found."}), 404
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An internal error occurred."}), 500

@app.route('/inventory/wine/consume', methods=['POST'])
def consume_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    personal_rating = data.get('personal_rating')
    if not vivino_url:
        return jsonify({'error': 'vivino_url is required'}), 400
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()
        if not wine_data_row:
            return jsonify({'error': 'Wine not found'}), 404
        wine_data_dict = dict(wine_data_row)
        current_quantity = wine_data_dict['quantity']
        wine_id = wine_data_dict['id']
        new_quantity = current_quantity
        if current_quantity > 0:
            new_quantity = current_quantity - 1
            if personal_rating is not None:
                cursor.execute("UPDATE wines SET quantity = ?, personal_rating = ? WHERE id = ?", (new_quantity, personal_rating, wine_id))
            else:
                cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine_id))
            sync_to_ha_todo(wine_data_dict, new_quantity)
        conn.commit()
        return jsonify({'status': 'success', 'new_quantity': new_quantity})
    finally:
        if conn: conn.close()

@app.route('/inventory/wine', methods=['DELETE'])
def delete_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing 'vivino_url'"}), 400
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_to_delete = cursor.fetchone()
        if wine_to_delete:
            wine_columns_description = cursor.description
        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        if cursor.rowcount > 0:
            if wine_to_delete and wine_columns_description:
                columns = [d[0] for d in wine_columns_description]
                wine_data_dict = dict(zip(columns, wine_to_delete))
                sync_to_ha_todo(wine_data_dict, 0)
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"status": "error", "message": "Wine not found."}), 404
    finally:
        if conn: conn.close()

@app.route('/api/rate-wine', methods=['POST'])
def rate_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    personal_rating = data.get('personal_rating')
    if not vivino_url or personal_rating is None:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    try:
        rating_val = float(personal_rating)
        if not (0 <= rating_val <= 5): raise ValueError("Rating out of bounds")
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid rating."}), 400
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE wines SET personal_rating = ? WHERE vivino_url = ?", (rating_val, vivino_url))
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "Wine not found"}), 404
        conn.commit()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        updated_wine_row = cursor.fetchone()
        if updated_wine_row:
            updated_wine_dict = dict(updated_wine_row)
            if updated_wine_dict['quantity'] > 0:
                sync_to_ha_todo(updated_wine_dict, updated_wine_dict['quantity'])
        return jsonify({"status": "success"}), 200
    finally:
        if conn: conn.close()

@app.route('/api/wine/notes', methods=['POST'])
def save_tasting_notes_and_image():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing required vivino_url"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Dynamically build the update query based on provided data
        updates = []
        params = []
        
        if 'tasting_notes' in data:
            updates.append("tasting_notes = ?")
            params.append(data['tasting_notes'])
            
        if 'image_url' in data:
            updates.append("image_url = ?")
            params.append(data['image_url'])

        if not updates:
            return jsonify({"status": "info", "message": "No data provided to update."}), 200

        query = f"UPDATE wines SET {', '.join(updates)} WHERE vivino_url = ?"
        params.append(vivino_url)
        
        cursor.execute(query, tuple(params))
        
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "Wine not found"}), 404
            
        conn.commit()
        return jsonify({"status": "success", "message": "Details saved."}), 200
    except sqlite3.Error as e:
        logger.error(f"Database error saving details: {e}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    finally:
        if conn: conn.close()

@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha():
    try:
        sync_db_to_ha_todo()
        return jsonify({"status": "success", "message": "All wines synchronized."}), 200
    except Exception as e:
        logger.error(f"Error during full sync: {e}")
        return jsonify({"status": "error", "message": "Internal error during sync."}), 500

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    try:
        reinitialize_database()
        return jsonify({"status": "success", "message": "Database reinitialized."}), 200
    except Exception as e:
        logger.error(f"Error reinitializing database: {e}")
        return jsonify({"status": "error", "message": "Internal error during reinitialization."}), 500

@app.route("/backup-database", methods=["POST"])
def backup_db_endpoint():
    """Creates a safe backup of the database to the /share directory."""
    backup_dir = os.path.dirname(DB_PATH) # e.g., /share/wwino
    backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")
    
    logger.info(f"Starting database backup from {DB_PATH} to {backup_path}")
    
    # Use SQLite's Online Backup API for a safe copy
    try:
        source_conn = sqlite3.connect(DB_PATH)
        backup_conn = sqlite3.connect(backup_path)
        
        with backup_conn:
            source_conn.backup(backup_conn)
            
        source_conn.close()
        backup_conn.close()
        
        logger.info("Database backup completed successfully.")
        return jsonify({"status": "success", "message": f"Backup successful! File saved in {backup_dir}."}), 200
    except sqlite3.Error as e:
        logger.error(f"Database backup failed: {e}")
        return jsonify({"status": "error", "message": "Database backup failed. Please try again later."}), 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during backup: {e}")
        return jsonify({"status": "error", "message": "An unexpected error occurred during backup."}), 500

@app.route("/restore-database", methods=["POST"])
def restore_db_endpoint():
    """Restores the database from the backup file in the /share directory."""
    backup_dir = os.path.dirname(DB_PATH)
    backup_path = os.path.join(backup_dir, "wonderful_wino_backup.db")

    if not os.path.exists(backup_path):
        logger.warning("Restore failed: Backup file not found at {backup_path}")
        return jsonify({"status": "error", "message": "Backup file not found. Please create a backup first."}), 404

    logger.info(f"Starting database restore from {backup_path} to {DB_PATH}")
    
    # Use SQLite's Online Backup API to safely overwrite the live DB
    try:
        source_conn = sqlite3.connect(backup_path)
        dest_conn = sqlite3.connect(DB_PATH)

        with dest_conn:
            source_conn.backup(dest_conn)

        source_conn.close()
        dest_conn.close()
        
        logger.info("Database restore completed successfully.")
        # Optionally, you could trigger a full sync to HA ToDo list after restore
        # sync_db_to_ha_todo() 
        return jsonify({"status": "success", "message": "Database restored successfully. The page will now refresh."}), 200
    except sqlite3.Error as e:
        logger.error(f"Database restore failed: {e}")
        return jsonify({"status": "error", "message": "Database restore failed. Please try again later."}), 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during restore: {e}")
        return jsonify({"status": "error", "message": "An unexpected error occurred. Please contact support."}), 500

@app.route("/")
def serve_frontend():
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)