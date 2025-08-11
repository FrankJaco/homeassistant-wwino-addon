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
class ReverseProxied:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

app.wsgi_app = ReverseProxied(app.wsgi_app)


# --- Helper Functions ---

def format_wine_for_todo(wine: dict) -> str:
    name = wine.get("name") or "n/a"
    vintage = wine.get("vintage")
    return f"{name} ({vintage})" if vintage else name

# PHASE 2 CHANGE: Updated description builder for new rating/cost display
def build_markdown_description(wine: dict, current_quantity: int) -> str:
    description_parts = []
    
    varietal_str = wine.get("varietal", "Unknown Varietal")
    if varietal_str and varietal_str != "Unknown Varietal":
        varietals = [v.strip() for v in varietal_str.split(',')]
        if varietals:
            description_parts.append(f"**{varietals[0]}**" + (f", {', '.join(varietals[1:])}" if len(varietals) > 1 else ""))
    
    region = wine.get("region", "Unknown Region")
    country = wine.get("country", "Unknown Country")
    location_parts = []
    if region and region != "Unknown Region":
        location_parts.append(f"**{region}**")
    if country and country != "Unknown Country":
        location_parts.append(country)
    if location_parts:
        description_parts.append(" ".join(location_parts))

    details_line = []
    
    vivino_rating = wine.get('vivino_rating')
    personal_rating = wine.get('personal_rating')
    display_rating = vivino_rating
    if personal_rating is not None and vivino_rating is not None:
        display_rating = (personal_rating + vivino_rating) / 2
    elif personal_rating is not None:
        display_rating = personal_rating

    if display_rating is not None:
        details_line.append(f"Quality: ⭐ **{display_rating:.1f}**")
        
    cost_tier = wine.get('cost_tier')
    if cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        details_line.append(f"Cost: **{''.join(['$'] * cost_tier)}**")

    details_line.append(f"Qty: [ **{current_quantity}** ]")
    
    description_parts.append("  |  ".join(details_line))

    return "  \n".join(description_parts)

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
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
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info(f"SQLite database initialized at {DB_PATH}")

def reinitialize_database():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        logger.warning("Dropping existing 'wines' table.")
        cursor.execute("DROP TABLE IF EXISTS wines")
        conn.commit()
        init_db()
        logger.info("Database reinitialized.")
    except sqlite3.Error as e:
        logger.error(f"Database error during reinitialization: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

# --- Home Assistant Sync ---
def sync_to_ha_todo(wine: dict, current_quantity: int) -> None:
    item_text = format_wine_for_todo(wine)
    description = build_markdown_description(wine, current_quantity)
    entity_id = TODO_LIST_ENTITY_ID
    headers = {
        "Authorization": f"Bearer {HA_LONG_LIVED_TOKEN}",
        "Content-Type": "application/json",
    }
    redacted_headers = {k: "Bearer [REDACTED]" if k == "Authorization" else v for k, v in headers.items()}

    remove_url = f"{HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    remove_payload = {"entity_id": entity_id, "item": item_text}
    logger.debug(f"HA To-Do remove request: URL={remove_url}, Payload={remove_payload}")
    try:
        requests.post(remove_url, json=remove_payload, headers=headers, timeout=5).raise_for_status()
        logger.info(f"HA To-Do removed (or attempted) for update: {item_text}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"HA To-Do remove attempt failed for '{item_text}'. This is often normal. Error: {e}")

    if current_quantity > 0:
        add_url = f"{HOME_ASSISTANT_URL}/api/services/todo/add_item"
        add_payload = {"entity_id": entity_id, "item": item_text, "description": description}
        logger.debug(f"HA To-Do add request: URL={add_url}, Payload={add_payload}")
        try:
            requests.post(add_url, json=add_payload, headers=headers, timeout=5).raise_for_status()
            logger.info(f"HA To-Do synchronized for: {item_text} with quantity {current_quantity}")
        except requests.exceptions.RequestException as e:
            logger.error(f"HA To-Do sync failed for add/update: {e}")
    else:
        logger.info(f"Wine quantity is 0. Item not re-added to HA To-Do: {item_text}")

# --- Vivino Scraping Logic ---
def scrape_vivino_data(vivino_url):
    logger.debug(f"Starting Vivino data scrape for URL: {vivino_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    wine_data = {
        'vivino_url': vivino_url, 'name': None, 'vintage': None, 'varietal': None,
        'region': None, 'country': None, 'vivino_rating': None, 'image_url': None
    }
    try:
        response = requests.get(vivino_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        script_tag = soup.find('script', type='application/ld+json')
        if script_tag:
            json_ld = json.loads(script_tag.string)
            if isinstance(json_ld, dict):
                wine_data['name'] = json_ld.get('name')
                wine_data['image_url'] = json_ld.get('image')
                if 'aggregateRating' in json_ld:
                    rating_val = json_ld['aggregateRating'].get('ratingValue')
                    if rating_val:
                        wine_data['vivino_rating'] = float(str(rating_val).replace(',', '.')) * 2
                if 'containsWine' in json_ld and 'vintage' in json_ld['containsWine']:
                    wine_data['vintage'] = int(json_ld['containsWine']['vintage'])

        if not wine_data['name']:
            name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine'))
            if name_tag:
                raw_name = " ".join(name_tag.text.strip().split())
                vintage_match = re.search(r'\b(19\d{2}|20\d{2})\b', raw_name)
                if vintage_match:
                    wine_data['vintage'] = int(vintage_match.group(0))
                    wine_data['name'] = raw_name.replace(vintage_match.group(0), '').strip()
                else:
                    wine_data['name'] = raw_name
        
        if not wine_data['vivino_rating']:
            rating_tag = soup.find('div', class_=re.compile(r'vivinoRating_averageValue'))
            if rating_tag:
                wine_data['vivino_rating'] = float(rating_tag.text.strip().replace(',', '.')) * 2

        for link in soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/')):
            href, text = link.get('href', ''), link.get_text(strip=True)
            if '/wine-countries/' in href and not wine_data['country']: wine_data['country'] = text
            elif '/wine-regions/' in href and not wine_data['region']: wine_data['region'] = text
            elif '/grapes/' in href and text and 'blend' not in text.lower():
                if not wine_data['varietal']: wine_data['varietal'] = text

        if wine_data['image_url'] and wine_data['image_url'].startswith('//'):
            wine_data['image_url'] = 'https:' + wine_data['image_url']

        for key in ['name', 'varietal', 'region', 'country']:
            if not wine_data[key]: wine_data[key] = f"Unknown {key.capitalize()}"

        logger.info(f"Scraped Vivino data for {wine_data.get('name', 'Unknown')}")
        return wine_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Vivino scrape error for {vivino_url}: {e}")
        return None

# --- Database Operations ---
# PHASE 2 CHANGE: Modified function signature to accept cost_tier
def insert_wine_data(wine_data, quantity=1, cost_tier=None):
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
                WHERE id = ?''', 
                (new_quantity, wine_data['name'], wine_data['vintage'], wine_data['varietal'], wine_data['region'], 
                 wine_data['country'], wine_data['vivino_rating'], wine_data['image_url'], cost_tier, wine_id))
            logger.info(f"Updated '{wine_data['name']}' quantity to {new_quantity}.")
        else:
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, image_url, quantity, cost_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (wine_data['vivino_url'], wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                 wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                 wine_data['image_url'], quantity, cost_tier))
            logger.info(f"Inserted new wine '{wine_data['name']}' with quantity {quantity}.")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"DB error inserting/updating data: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# --- Flask Routes ---
@app.route('/scan-wine', methods=['POST'])
def scan_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    quantity = data.get('quantity', 1)
    cost_tier = data.get('cost_tier')
    if not vivino_url: return jsonify({"status": "error", "message": "Missing 'vivino_url'"}), 400

    wine_data = scrape_vivino_data(vivino_url)
    if not wine_data: return jsonify({"status": "error", "message": "Failed to scrape Vivino data."}), 500

    if insert_wine_data(wine_data, quantity, cost_tier):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (wine_data['vivino_url'],))
        final_wine_state = cursor.fetchone()
        conn.close()
        if final_wine_state:
            sync_to_ha_todo(dict(final_wine_state), final_wine_state['quantity'])
            return jsonify({"status": "success", "message": "Wine scraped and stored."}), 200
    return jsonify({"status": "error", "message": "Failed to store wine data."}), 500

@app.route('/add-manual-wine', methods=['POST'])
def add_manual_wine():
    data = request.get_json()
    if not all(k in data for k in ['name', 'vintage', 'quantity']):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', data['name'].replace(' ', '_')).lower()
    synthetic_url = f"manual:{safe_name}:{data['vintage']}"
    
    wine_data = {'vivino_url': synthetic_url, 'name': data['name'], 'vintage': data['vintage'],
                 'varietal': data.get('varietal', "Unknown Varietal"), 'region': data.get('region', "Unknown Region"),
                 'country': data.get('country', "Unknown Country"), 'vivino_rating': None, 'image_url': None}
    
    if insert_wine_data(wine_data, data['quantity'], data.get('cost_tier')):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (synthetic_url,))
        final_wine_state = cursor.fetchone()
        conn.close()
        if final_wine_state:
            sync_to_ha_todo(dict(final_wine_state), final_wine_state['quantity'])
            return jsonify({"status": "success", "message": "Wine manually added."}), 200
    return jsonify({"status": "error", "message": "Failed to store manual wine data."}), 500

@app.route('/edit-wine', methods=['POST'])
def edit_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url: return jsonify({"status": "error", "message": "Missing vivino_url"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        old_wine_row = cursor.fetchone()
        if old_wine_row:
            sync_to_ha_todo(dict(old_wine_row), 0)
        else:
            return jsonify({"status": "error", "message": "Wine to edit not found."}), 404

        # PHASE 2 CHANGE: Update cost_tier in the UPDATE statement
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, quantity = ?, cost_tier = ?
            WHERE vivino_url = ?''',
            (data.get('name'), data.get('vintage'), data.get('varietal'), data.get('region'), 
             data.get('country'), data.get('quantity'), data.get('cost_tier'), vivino_url))
        conn.commit()

        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        updated_wine_row = cursor.fetchone()
        if updated_wine_row:
            sync_to_ha_todo(dict(updated_wine_row), updated_wine_row['quantity'])
        
        return jsonify({"status": "success", "message": "Wine updated."}), 200
    except sqlite3.Error as e:
        logger.error(f"DB error editing wine {vivino_url}: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "DB error during edit."}), 500
    finally:
        if conn: conn.close()

@app.route('/inventory', methods=['GET'])
def get_inventory():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    filter_param = request.args.get('filter', 'on_hand')
    
    query = "SELECT * FROM wines"
    if filter_param == 'on_hand':
        query += " WHERE quantity > 0"
    elif filter_param == 'history':
        query += " WHERE quantity = 0"
    
    query += " ORDER BY added_at DESC"
    
    try:
        cursor.execute(query)
        wines = [dict(row) for row in cursor.fetchall()]
        conn.close()
        logger.info(f"Returning {len(wines)} wines with filter '{filter_param}'.")
        return jsonify(wines), 200
    except sqlite3.Error as e:
        logger.error(f"DB error retrieving inventory: {e}")
        return jsonify({"status": "error", "message": "Database error."}), 500

@app.route('/inventory/wine/consume', methods=['POST'])
def consume_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url: return jsonify({'error': 'vivino_url is required'}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine = cursor.fetchone()
        if not wine: return jsonify({'error': 'Wine not found'}), 404

        if wine['quantity'] > 0:
            new_quantity = wine['quantity'] - 1
            cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine['id']))
            conn.commit()
            sync_to_ha_todo(dict(wine), new_quantity)
            return jsonify({'status': 'success', 'new_quantity': new_quantity})
        
        return jsonify({'status': 'warning', 'message': 'Quantity already zero'}), 200
    except sqlite3.Error as e:
        logger.error(f"DB error consuming wine: {e}")
        conn.rollback()
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn: conn.close()

@app.route('/inventory/wine', methods=['DELETE'])
def delete_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url: return jsonify({"status": "error", "message": "Missing 'vivino_url'"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_to_delete = cursor.fetchone()
        if not wine_to_delete: return jsonify({"status": "error", "message": "Wine not found"}), 404

        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        
        sync_to_ha_todo(dict(wine_to_delete), 0)
        logger.info(f"Successfully deleted wine: {vivino_url}")
        return jsonify({"status": "success", "message": "Wine deleted successfully."}), 200
    except sqlite3.Error as e:
        logger.error(f"DB error deleting wine: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error deleting wine."}), 500
    finally:
        if conn: conn.close()
        
@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha():
    return jsonify({"status": "success", "message": "Sync triggered."}), 200

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    logger.warning("Received request to reinitialize database.")
    try:
        reinitialize_database()
        return jsonify({"status": "success", "message": "Database reinitialized."}), 200
    except Exception as e:
        logger.error(f"Error reinitializing database: {e}")
        return jsonify({"status": "error", "message": "An internal error occurred."}), 500

@app.route("/")
def serve_frontend():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    init_db()
    logger.info("Flask app starting on port 5000...")
    app.run(host='0.0.0.0', port=5000)