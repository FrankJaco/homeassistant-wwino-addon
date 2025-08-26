import os
import logging
from flask import Flask, request, jsonify, send_from_directory, Response
import sqlite3
import requests
from bs4 import BeautifulSoup
import re # For regular expressions to clean strings
import json # For parsing JSON-LD data from Vivino
from flask_cors import CORS # Re-enabled CORS
from urllib.parse import urlparse, parse_qs
import time # For generating unique IDs for manual entries
import queue

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

# --- SSE Setup ---
subscriptions = []
def push_event(message: str):
    """Pushes a message string (JSON) to all connected SSE clients."""
    for q in subscriptions[:]: # Iterate over a copy
        try:
            q.put_nowait(message)
        except queue.Full:
            try:
                subscriptions.remove(q)
            except ValueError:
                # Subscriber already removed by another thread
                pass

@app.route('/events')
def sse_events():
    """SSE endpoint for frontend to subscribe to."""
    def stream():
        q = queue.Queue()
        subscriptions.append(q)
        try:
            while True:
                msg = q.get()
                yield f"data: {msg}\n\n"
        except GeneratorExit:
            try:
                subscriptions.remove(q)
            except ValueError:
                pass # Already removed
    return Response(stream(), mimetype='text/event-stream')


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


# Dictionary for common country abbreviations for display purposes
COUNTRY_ABBREVIATIONS = {
    "United States": "US", "Australia": "AU", "France": "FR", "New Zealand": "NZ",
    "Italy": "IT", "Spain": "ES", "Argentina": "AR", "Chile": "CL", "Germany": "DE",
    "Portugal": "PT", "South Africa": "ZA", "Canada": "CA", "United Kingdom": "UK",
    "Austria": "AT", "Greece": "GR", "Hungary": "HU", "Lebanon": "LB", "Mexico": "MX",
    "Moldova": "MD", "Romania": "RO", "Switzerland": "CH", "Turkey": "TR", "Uruguay": "UY",
}


def format_wine_for_todo(wine: dict) -> str:
    name = wine.get("name") or "n/a"
    vintage = wine.get("vintage")
    return f"{name} ({vintage})" if vintage else name

def build_markdown_description(wine: dict, current_quantity: int, is_for_todo: bool = True) -> str:
    description_parts = []
    varietal_str = wine.get("varietal")
    rendered_varietal_line_markdown = []
    current_visual_length = 0
    MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL = 32
    TRUNCATION_THRESHOLD_PERCENT = 0.60
    if varietal_str and varietal_str != "Unknown Varietal":
        individual_varietals = [v.strip() for v in varietal_str.split(',')]
        if individual_varietals:
            if is_for_todo:
                first_grape = individual_varietals[0]
                if len(first_grape) <= MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL:
                    rendered_varietal_line_markdown.append(f"**{first_grape}**")
                    current_visual_length += len(first_grape)
                else:
                    truncated_grape = first_grape[:MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL]
                    rendered_varietal_line_markdown.append(f"**{truncated_grape}**")
                    current_visual_length += len(truncated_grape)
                for i, grape in enumerate(individual_varietals[1:]):
                    if not rendered_varietal_line_markdown and i > 0: break
                    separator = " " if i == 0 else ", "
                    remaining_space = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - current_visual_length
                    if remaining_space >= (len(separator) + len(grape)):
                        rendered_varietal_line_markdown.append(f"{separator}{grape}")
                        current_visual_length += len(separator) + len(grape)
                    else:
                        space_for_grape = remaining_space - len(separator)
                        if space_for_grape > 0 and (space_for_grape / len(grape)) >= TRUNCATION_THRESHOLD_PERCENT:
                            rendered_varietal_line_markdown.append(f"{separator}{grape[:space_for_grape]}")
                        break
            else:
                rendered_varietal_line_markdown.append(f"**{individual_varietals[0]}**")
                if len(individual_varietals) > 1:
                    rendered_varietal_line_markdown.append(f", {', '.join(individual_varietals[1:])}")
    if rendered_varietal_line_markdown:
        description_parts.append("".join(rendered_varietal_line_markdown))
    else:
        description_parts.append("Unknown Varietal")
    region_str = wine.get("region")
    country_str = wine.get("country")
    MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY = 32
    region_country_display = []
    current_rc_visual_length = 0
    if region_str and region_str != "Unknown Region":
        region_country_display.append(f"**{region_str}**")
        current_rc_visual_length += len(region_str)
    if country_str and country_str != "Unknown Country":
        separator = " "
        if is_for_todo:
            full_country_segment = f"{separator}{country_str}"
            if (current_rc_visual_length + len(full_country_segment)) <= MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY:
                region_country_display.append(full_country_segment)
            else:
                abbr_country = COUNTRY_ABBREVIATIONS.get(country_str, country_str)
                abbr_country_segment = f"{separator}{abbr_country}"
                if (current_rc_visual_length + len(abbr_country_segment)) <= MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY:
                    region_country_display.append(abbr_country_segment)
                else:
                    space_for_country = MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY - current_rc_visual_length - len(separator)
                    if space_for_country > 0:
                        region_country_display.append(f"{separator}{country_str[:space_for_country]}")
        else:
            region_country_display.append(f"{separator}{country_str}")
    if region_country_display:
        description_parts.append("".join(region_country_display))
    else:
        description_parts.append("Unknown Region/Country")
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
    return "  \n".join(description_parts[:3]) if is_for_todo else "  \n".join(description_parts)

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
        logger.warning("Attempting to reinitialize the database: Dropping existing 'wines' table.")
        cursor.execute("DROP TABLE IF EXISTS wines")
        conn.commit()
        logger.info("Successfully dropped 'wines' table (if it existed).")
        init_db()
        logger.info("Successfully re-created database tables using init_db().")
    except sqlite3.Error as e:
        logger.error(f"Database error during reinitialization: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

def sync_to_ha_todo(wine: dict, current_quantity: int) -> None:
    item_text = format_wine_for_todo(wine)
    description = build_markdown_description(wine, current_quantity, is_for_todo=True)
    entity_id = TODO_LIST_ENTITY_ID
    headers = {"Authorization": f"Bearer {HA_LONG_LIVED_TOKEN}", "Content-Type": "application/json"}
    redacted_headers = headers.copy()
    if "Authorization" in redacted_headers: redacted_headers["Authorization"] = "Bearer [REDACTED]"
    remove_url = f"{HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    remove_payload = {"entity_id": entity_id, "item": item_text}
    logger.debug(f"HA To-Do remove_item request: URL={remove_url}, Headers={redacted_headers}, Payload={remove_payload}")
    try:
        resp = requests.post(remove_url, json=remove_payload, headers=headers, timeout=5)
        resp.raise_for_status()
        logger.info(f"HA To-Do removed (or attempted to remove) for update/deletion: {item_text}")
    except requests.exceptions.HTTPError as http_e:
        if http_e.response.status_code == 500 and "Unable to find to-do list item" in http_e.response.text:
            logger.warning(f"HA To-Do remove attempt failed (Item Not Found) for '{item_text}'.")
        else:
            logger.error(f"HA To-Do remove attempt failed (HTTP Error) for '{item_text}'.")
    except Exception as e:
        logger.warning(f"HA To-Do remove attempt failed for '{item_text}'.")

    if current_quantity > 0:
        add_url = f"{HOME_ASSISTANT_URL}/api/services/todo/add_item"
        add_payload = {"entity_id": entity_id, "item": item_text, "description": description}
        logger.debug(f"HA To-Do add_item request: URL={add_url}, Headers={redacted_headers}, Payload={add_payload}")
        try:
            resp = requests.post(add_url, json=add_payload, headers=headers, timeout=5)
            resp.raise_for_status()
            logger.info(f"HA To-Do synchronized (re-added/updated) for: {item_text} with quantity {current_quantity}")
        except requests.exceptions.HTTPError as http_e:
            logger.error(f"HA To-Do sync failed for add/update (HTTP Error): {item_text}.")
        except Exception as e:
            logger.error(f"HA To-Do sync failed for add/update: {e}")
    else:
        logger.info(f"Wine quantity is 0. Item not re-added to HA To-Do: {item_text}")

def scrape_vivino_data(vivino_url):
    logger.debug(f"Starting Vivino data scrape for URL: {vivino_url}")
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    ]
    headers = {'User-Agent': user_agents[0]}
    wine_data = {'vivino_url': vivino_url, 'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal', 'region': 'Unknown Region', 'country': 'Unknown Country', 'vivino_rating': None, 'image_url': None}
    all_grape_names_collected = []
    try:
        response = requests.get(vivino_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                json_ld = json.loads(script.string)
                if isinstance(json_ld, dict):
                    if json_ld.get('@type') == 'Product':
                        if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld: wine_data['name'] = json_ld['name'].strip()
                        if wine_data['image_url'] is None and 'image' in json_ld:
                            if isinstance(json_ld['image'], list) and json_ld['image']: wine_data['image_url'] = json_ld['image'][0]
                            elif isinstance(json_ld['image'], str): wine_data['image_url'] = json_ld['image']
                        aggregate_rating = json_ld.get('aggregateRating')
                        if aggregate_rating and isinstance(aggregate_rating, dict):
                            if wine_data['vivino_rating'] is None:
                                rating_value = aggregate_rating.get('ratingValue')
                                if rating_value is not None:
                                    try: wine_data['vivino_rating'] = float(str(rating_value).replace(',', '.'))
                                    except ValueError: pass
                        contains_wine = json_ld.get('containsWine')
                        if contains_wine and isinstance(contains_wine, dict) and contains_wine.get('@type') == 'Wine':
                            if wine_data['vintage'] is None and 'vintage' in contains_wine:
                                try: wine_data['vintage'] = int(contains_wine['vintage'])
                                except ValueError: pass
                            grapes = contains_wine.get('grape')
                            if grapes:
                                if isinstance(grapes, list):
                                    grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                    if grape_names: all_grape_names_collected.extend(grape_names)
                                elif isinstance(grapes, dict) and 'name' in grapes:
                                    all_grape_names_collected.append(grapes['name'].strip())
                        main_entity_of_page = json_ld.get('mainEntityOfPage')
                        if main_entity_of_page and isinstance(main_entity_of_page, dict):
                            breadcrumb = main_entity_of_page.get('breadcrumb')
                            if breadcrumb and isinstance(breadcrumb, dict) and breadcrumb.get('@type') == 'BreadcrumbList':
                                item_list = breadcrumb.get('itemListElement')
                                if item_list and isinstance(item_list, list):
                                    for item_elem in item_list:
                                        if isinstance(item_elem, dict) and 'item' in item_elem:
                                            item = item_elem['item']
                                            if isinstance(item, dict) and 'name' in item and 'url' in item:
                                                if wine_data['country'] == 'Unknown Country' and '/countries/' in item['url']: wine_data['country'] = item['name'].strip()
                                                if wine_data['region'] == 'Unknown Region' and '/regions/' in item['url']: wine_data['region'] = item['name'].strip()
            except (json.JSONDecodeError, KeyError, TypeError) as json_err:
                logger.debug(f"Vivino JSON-LD parsing error: {json_err}")
                pass
        if wine_data['image_url'] is None:
            preload_links = soup.find_all('link', rel='preload', attrs={'as': 'image'})
            best_image_url = None
            if preload_links:
                for link in preload_links:
                    if link.has_attr('imagesrcset'):
                        srcset_parts = [url.strip().split(' ')[0] for url in link['imagesrcset'].split(',')]
                        if srcset_parts: best_image_url = srcset_parts[-1]; break
                    elif link.has_attr('href'): best_image_url = link['href']
                if best_image_url: wine_data['image_url'] = best_image_url
        if wine_data['image_url'] is None:
            image_tag = soup.find('img', class_=re.compile(r'wine-page-image__image|vivinoImage_image|image-preview__image|image-container__image|wine-page__image'))
            if image_tag:
                if image_tag.has_attr('src'): wine_data['image_url'] = image_tag['src']
                elif image_tag.has_attr('data-src'): wine_data['image_url'] = image_tag['data-src']
        if wine_data['image_url'] and wine_data['image_url'].startswith('//'): wine_data['image_url'] = 'https:' + wine_data['image_url']
        if wine_data['name'] == 'Unknown Wine':
            name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine'))
            if not name_tag: name_tag = soup.find('h1')
            if name_tag: wine_data['name'] = " ".join(name_tag.text.strip().split())
        if wine_data['vintage'] is None and wine_data['name'] and 'Unknown Wine' not in wine_data['name']:
            name_vintage_match = re.search(r'\b(19\d{2}|20\d{2})\b', wine_data['name'])
            if name_vintage_match:
                try:
                    year = int(name_vintage_match.group(0))
                    if 1900 <= year <= 2030:
                        wine_data['vintage'] = year
                        cleaned_name = wine_data['name'].replace(name_vintage_match.group(0), '').strip()
                        wine_data['name'] = " ".join(cleaned_name.split())
                except ValueError: pass
        if wine_data['vintage'] is None:
            vintage_span = soup.find('span', class_='vintage')
            if vintage_span:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', vintage_span.text.strip())
                if year_match:
                    try: wine_data['vintage'] = int(year_match.group(0))
                    except ValueError: pass
        all_relevant_links = soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/'))
        for link in all_relevant_links:
            href, text = link.get('href', ''), link.get_text(strip=True)
            if '/wine-countries/' in href and wine_data['country'] == 'Unknown Country': wine_data['country'] = text
            elif '/wine-regions/' in href and wine_data['region'] == 'Unknown Region': wine_data['region'] = text
            elif '/grapes/' in href and text and 'blend' not in text.lower() and 'wine' not in text.lower(): all_grape_names_collected.append(text)
        if all_grape_names_collected:
            seen_grapes = set()
            ordered_unique_grapes = []
            for grape in all_grape_names_collected:
                cleaned_grape = grape.strip()
                if cleaned_grape.lower() not in ['red wine', 'white wine', 'sparkling wine', 'rosé wine', 'dessert wine', 'fortified wine', 'blend'] and cleaned_grape not in seen_grapes:
                    ordered_unique_grapes.append(cleaned_grape)
                    seen_grapes.add(cleaned_grape)
            if ordered_unique_grapes: wine_data['varietal'] = ", ".join(ordered_unique_grapes)
        if wine_data['vivino_rating'] is None:
            rating_tags = soup.find_all('div', class_=re.compile(r'vivinoRating_averageValue|average-value|community-score__score|rating-value'))
            for rating_tag in rating_tags:
                try:
                    rating_text = rating_tag.text.strip().replace(',', '.')
                    if rating_text: wine_data['vivino_rating'] = float(rating_text); break
                except ValueError: pass
        return wine_data
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP/Network error during Vivino scrape for {vivino_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Vivino scrape for {vivino_url}: {e}")
        return None

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
                UPDATE wines SET quantity = ?, name = ?, vintage = ?, varietal = ?, region = ?, country = ?,
                    vivino_rating = ?, image_url = ?, cost_tier = ?, added_at = CURRENT_TIMESTAMP
                WHERE id = ?''',
                (new_quantity, wine_data['name'], wine_data['vintage'], wine_data['varietal'], wine_data['region'],
                 wine_data['country'], wine_data['vivino_rating'], wine_data['image_url'], cost_tier, wine_id))
            logger.info(f"Updated quantity for '{wine_data['name']}' to {new_quantity}.")
        else:
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, image_url, quantity, cost_tier, personal_rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (wine_data['vivino_url'], wine_data['name'], wine_data['vintage'], wine_data['varietal'],
                 wine_data['region'], wine_data['country'], wine_data['vivino_rating'],
                 wine_data['image_url'], quantity, cost_tier, None))
            logger.info(f"New wine '{wine_data['name']}' inserted with quantity {quantity}.")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error inserting/updating wine data for {wine_data.get('name', 'N/A')}: {e}")
        conn.rollback()
        return False
    finally:
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
    logger.info(f"Received request to process Vivino URL: {vivino_url} with quantity: {quantity}")
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
        logger.info(f"Found existing wine '{wine_data['name']}' ({wine_data['vintage']}) with URL {existing_wine_dict['vivino_url']}. Consolidating.")
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
            return jsonify({"status": "success", "message": "Wine data scraped and stored/updated.", "wine_name": updated_wine_dict['name'], "vintage": updated_wine_dict['vintage'], "vivino_url": canonical_url_for_update, "quantity_added": quantity, "current_total_quantity": current_total_quantity}), 200
        else:
            return jsonify({"status": "error", "message": "Failed to retrieve wine after update."}), 500
    else:
        return jsonify({"status": "error", "message": "Failed to store/update wine data in database."}), 500

@app.route('/add-manual-wine', methods=['POST'])
def add_manual_wine():
    data = request.get_json()
    required_fields = ['name', 'vintage', 'quantity']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    quantity = data.get('quantity', 1)
    if not isinstance(quantity, int) or quantity < 1: quantity = 1
    cost_tier = data.get('cost_tier')
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', data['name'].replace(' ', '_')).lower()
    synthetic_url = f"manual:{safe_name}:{data['vintage']}"
    logger.info(f"Received request to manually add wine: {data['name']} ({data['vintage']})")
    wine_data = {'vivino_url': synthetic_url, 'name': data['name'], 'vintage': data['vintage'], 'varietal': data.get('varietal') or "Unknown Varietal", 'region': data.get('region') or "Unknown Region", 'country': data.get('country') or "Unknown Country", 'vivino_rating': None, 'image_url': None, 'cost_tier': cost_tier, 'personal_rating': None}
    if insert_wine_data(wine_data, quantity, cost_tier):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM wines WHERE vivino_url = ?", (synthetic_url,))
        current_total_quantity_row = cursor.fetchone()
        conn.close()
        current_total_quantity = current_total_quantity_row[0] if current_total_quantity_row else quantity
        sync_to_ha_todo(wine_data, current_total_quantity)
        return jsonify({"status": "success", "message": "Wine manually added/updated.", "wine_name": wine_data['name'], "vintage": wine_data['vintage'], "vivino_url": wine_data['vivino_url'], "current_total_quantity": current_total_quantity}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to store manual wine data."}), 500

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
            sync_to_ha_todo(dict(old_wine_row), 0)
        else:
            return jsonify({"status": "error", "message": "Wine to edit not found."}), 404
        cursor.execute('''
            UPDATE wines SET name = ?, vintage = ?, varietal = ?, region = ?, country = ?, 
                quantity = ?, cost_tier = ?, personal_rating = ?
            WHERE vivino_url = ?''',
            (data['name'], data['vintage'], data.get('varietal') or "Unknown Varietal", data.get('region') or "Unknown Region",
             data.get('country') or "Unknown Country", data['quantity'], data.get('cost_tier'), data.get('personal_rating'), vivino_url))
        conn.commit()
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        updated_wine_row = cursor.fetchone()
        if updated_wine_row:
            sync_to_ha_todo(dict(updated_wine_row), updated_wine_row['quantity'])
        logger.info(f"Successfully edited wine: {vivino_url}")
        return jsonify({"status": "success", "message": "Wine updated successfully."}), 200
    except sqlite3.Error as e:
        logger.error(f"Database error editing wine {vivino_url}: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error while editing wine."}), 500
    finally:
        if conn: conn.close()

@app.route('/inventory', methods=['GET'])
def get_inventory():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    name_filter = request.args.get('name')
    vintage_filter = request.args.get('vintage')
    status_filter = request.args.get('filter', 'on_hand')
    query = "SELECT * FROM wines"
    params = []
    conditions = []
    if status_filter == 'on_hand': conditions.append("quantity > 0")
    elif status_filter == 'history': conditions.append("quantity = 0")
    if name_filter:
        conditions.append("name LIKE ?")
        params.append(f"%{name_filter}%")
    if vintage_filter:
        conditions.append("vintage = ?")
        params.append(vintage_filter)
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY added_at DESC"
    try:
        cursor.execute(query, params)
        wines = cursor.fetchall()
        wine_list = [dict(wine_row) for wine_row in wines]
        logger.info(f"Returning {len(wine_list)} wines from inventory with filter: {status_filter}")
        return jsonify(wine_list), 200
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving inventory: {e}")
        return jsonify({"status": "error", "message": "Database error retrieving inventory."}), 500
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
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()
        if wine_data_row:
            wine_data_dict = dict(wine_data_row)
            cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
            conn.commit()
            if cursor.rowcount > 0:
                sync_to_ha_todo(wine_data_dict, new_quantity)
                return jsonify({"status": "success", "message": f"Quantity for wine set to {new_quantity}."}), 200
            else: return jsonify({"status": "error", "message": "Wine not found for quantity update."}), 404
        else: return jsonify({"status": "error", "message": "Wine not found for quantity update."}), 404
    except sqlite3.Error as e:
        logger.error(f"Database error setting wine quantity: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error setting wine quantity."}), 500
    finally:
        if conn: conn.close()

@app.route('/inventory/wine/consume', methods=['POST'])
def consume_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    personal_rating = data.get('personal_rating')
    if not vivino_url: return jsonify({'error': 'vivino_url is required'}), 400
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()
        if not wine_data_row: return jsonify({'error': 'Wine not found in inventory'}), 404
        wine_data_dict = dict(wine_data_row)
        current_quantity = wine_data_dict['quantity']
        wine_id = wine_data_dict['id']
        if current_quantity > 0:
            new_quantity = current_quantity - 1
            if personal_rating is not None:
                cursor.execute("UPDATE wines SET quantity = ?, personal_rating = ? WHERE id = ?", (new_quantity, personal_rating, wine_id))
                wine_data_dict['personal_rating'] = personal_rating
            else:
                cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine_id))
            sync_to_ha_todo(wine_data_dict, new_quantity)
        else:
            new_quantity = 0
        conn.commit()
        return jsonify({'status': 'success', 'new_quantity': new_quantity})
    except sqlite3.Error as e:
        logger.error(f"Database error during consumption: {e}")
        conn.rollback()
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn: conn.close()

@app.route('/inventory/wine', methods=['DELETE'])
def delete_wine():
    data = request.get_json()
    if not data or 'vivino_url' not in data:
        return jsonify({"status": "error", "message": "Missing 'vivino_url' in request body"}), 400
    vivino_url = data['vivino_url']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_to_delete = cursor.fetchone()
        wine_columns_description = None
        if wine_to_delete: wine_columns_description = cursor.description
        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        if cursor.rowcount > 0:
            if wine_to_delete and wine_columns_description:
                columns = [description[0] for description in wine_columns_description]
                wine_data_dict = dict(zip(columns, wine_to_delete))
                sync_to_ha_todo(wine_data_dict, 0)
            return jsonify({"status": "success", "message": "Wine deleted successfully."}), 200
        else: return jsonify({"status": "error", "message": "Wine not found for deletion."}), 404
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error deleting wine."}), 500
    finally:
        if conn: conn.close()

@app.route('/api/consume-wine', methods=['POST'])
def consume_wine_from_webhook():
    """
    Webhook endpoint called by HA automation when a To-Do item is completed.
    Parses wine name + vintage, decrements DB, pushes SSE events to frontend.
    """
    try:
        data = request.get_json()
        if not data or "item" not in data:
            return jsonify({"status": "error", "message": "Missing 'item' in request body"}), 400

        item_text = data["item"]
        parsed_name, parsed_vintage = None, None
        if item_text.endswith(")") and item_text[-6:-5] == "(" and item_text[-5:-1].isdigit() and len(item_text) > 6:
            try:
                parsed_vintage = int(item_text[-5:-1])
                parsed_name = item_text[:-6].rstrip()
            except (ValueError, IndexError):
                parsed_name = item_text.strip()
        else:
            parsed_name = item_text.strip()
        name, vintage = parsed_name, parsed_vintage

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            if vintage is not None:
                cursor.execute("SELECT * FROM wines WHERE name = ? AND vintage = ?", (name, vintage))
            else:
                cursor.execute("SELECT * FROM wines WHERE name = ? AND vintage IS NULL", (name,))
            wine_record = cursor.fetchone()

            if wine_record:
                wine_data = dict(wine_record)
                current_db_quantity = wine_data.get("quantity", 0)
                if current_db_quantity > 0:
                    new_quantity = current_db_quantity - 1
                    cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine_data["id"]))
                    conn.commit()

                    push_event(json.dumps({"type": "refresh_inventory"}))
                    push_event(json.dumps({
                        "type": "open_rating",
                        "vivino_url": wine_data["vivino_url"],
                        "name": wine_data["name"],
                        "vintage": wine_data["vintage"]
                    }))
                    return jsonify({"status": "success", "message": f"Quantity updated. New quantity: {new_quantity}."}), 200
                else:
                    return jsonify({"status": "warning", "message": "Quantity already zero."}), 404
            return jsonify({"status": "warning", "message": "No matching wine found in DB."}), 404
        except sqlite3.Error as e:
            conn.rollback()
            return jsonify({"status": "error", "message": f"DB error: {e}"}), 500
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Webhook processing error: {e}"}), 500

@app.route('/inventory/wine/rate', methods=['POST'])
def rate_wine():
    """
    Accepts { vivino_url, personal_rating } and updates the DB rating
    without decrementing quantity.
    """
    data = request.get_json()
    vivino_url = data.get("vivino_url")
    personal_rating = data.get("personal_rating")

    if not vivino_url or personal_rating is None:
        return jsonify({"error": "vivino_url and personal_rating are required"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()
        if not wine_data_row:
            return jsonify({"error": "Wine not found in inventory"}), 404

        wine_id = wine_data_row["id"]
        cursor.execute("UPDATE wines SET personal_rating = ? WHERE id = ?", (personal_rating, wine_id))
        conn.commit()

        push_event(json.dumps({"type": "refresh_inventory"}))
        return jsonify({"status": "success", "message": "Rating updated"}), 200
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        conn.close()

@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha():
    logger.info("Received request to sync all wines to Home Assistant.")
    try:
        sync_db_to_ha_todo()
        return jsonify({"status": "success", "message": "All wines synchronized to Home Assistant."}), 200
    except Exception as e:
        logger.error(f"Error during full synchronization to Home Assistant: {e}")
        return jsonify({"status": "error", "message": "An internal error occurred during synchronization."}), 500

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    logger.warning("Received request to reinitialize database from web UI.")
    try:
        reinitialize_database()
        return jsonify({"status": "success", "message": "Database reinitialized successfully. Please restart add-on from Home Assistant if needed."}), 200
    except Exception as e:
        logger.error(f"Error reinitializing database from web UI: {e}")
        return jsonify({"status": "error", "message": "An internal error occurred while reinitializing the database."}), 500

@app.route("/")
def serve_frontend():
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)

# --- Application Entry Point ---
if __name__ == '__main__':
    reinitialize_flag = os.environ.get("REINITIALIZE_DATABASE", "false").lower()
    logger.debug(f"DEBUG: REINITIALIZE_DATABASE as read by app: '{reinitialize_flag}'")
    logger.info(f"Flask app using HOME_ASSISTANT_URL: '{HOME_ASSISTANT_URL}'")
    if __name__ == '__main__':
        logger.info("Ensuring database tables exist.")
        init_db()
    logger.info("Flask app starting on port 5000...")
    app.run(host='0.0.0.0', port=5000)
