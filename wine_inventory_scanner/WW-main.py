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

# --- Configuration (read from environment variables) ---
HOME_ASSISTANT_URL = os.environ.get("HOME_ASSISTANT_URL")
HA_LONG_LIVED_TOKEN = os.environ.get("HA_LONG_LIVED_TOKEN")
TODO_LIST_ENTITY_ID = os.environ.get("TODO_LIST_ENTITY_ID")
DB_PATH = os.environ.get("DB_PATH", "/share/wine_inventory.db") # Default to /share if not set
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
    ELLIPSIS_LENGTH = 0 # Not used for visual length, but kept for context

    if varietal_str and varietal_str != "Unknown Varietal":
        individual_varietals = [v.strip() for v in varietal_str.split(',')]

        if individual_varietals:
            if is_for_todo:
                # --- Handle the first grape (bolded) for ToDo truncation ---
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
                    if not rendered_varietal_line_markdown and i > 0: # If first grape was too long, don't add more
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
                # For full display, just join all varietals
                rendered_varietal_line_markdown.append(f"**{individual_varietals[0]}**")
                if len(individual_varietals) > 1:
                    rendered_varietal_line_markdown.append(f", {', '.join(individual_varietals[1:])}")

    if rendered_varietal_line_markdown:
        description_parts.append("".join(rendered_varietal_line_markdown))
    else:
        description_parts.append("Unknown Varietal")


    # Line 2: Region, Country (bold region, un-bold country, conditional abbreviation)
    region_str = wine.get("region")
    country_str = wine.get("country")

    MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY = 32 # Same limit as varietal line

    region_country_display = []
    current_rc_visual_length = 0

    if region_str and region_str != "Unknown Region":
        # Add region, always bolded
        region_country_display.append(f"**{region_str}**")
        current_rc_visual_length += len(region_str) # Only count visual chars

    if country_str and country_str != "Unknown Country":
        separator_rc = " " # Always a single space between region and country

        if is_for_todo:
            # First, try to add the full country name
            potential_full_country_segment = f"{separator_rc}{country_str}"
            if (current_rc_visual_length + len(potential_full_country_segment)) <= MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY:
                region_country_display.append(potential_full_country_segment)
            else:
                # Full country doesn't fit. Try abbreviation.
                abbreviated_country = COUNTRY_ABBREVIATIONS.get(country_str, country_str)
                potential_abbr_country_segment = f"{separator_rc}{abbreviated_country}"

                if (current_rc_visual_length + len(potential_abbr_country_segment)) <= MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY:
                    region_country_display.append(potential_abbr_country_segment)
                else:
                    # Even abbreviation doesn't fit, or no abbreviation. Truncate country.
                    space_for_country_body = MAX_VISUAL_LINE_LENGTH_FOR_REGION_COUNTRY - current_rc_visual_length - len(separator_rc)
                    if space_for_country_body > 0:
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


    # Line 3: Quantity and Vivino Rating (combined)
    rating_qty_line_parts = []

    # Add quantity first to the last line
    rating_qty_line_parts.append(f"Qty: [ **{current_quantity}** ]")

    if wine.get("vivino_rating") is not None and wine.get("vivino_num_ratings"):
        rating_qty_line_parts.append(f"Rating: **{wine['vivino_rating']:.1f}** ⭐ ({wine['vivino_num_ratings']})")
    elif wine.get("vivino_rating") is not None:
         rating_qty_line_parts.append(f"Rating: **{wine['vivino_rating']:.1f}** ⭐")

    description_parts.append("&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;".join(rating_qty_line_parts))

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
            vivino_num_ratings INTEGER,
            price_usd REAL,
            image_url TEXT,
            quantity INTEGER DEFAULT 1, -- New column for quantity
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


# --- Vivino Scraping Logic ---
def scrape_vivino_data(vivino_url):
    """
    Scrapes detailed wine information from a given Vivino URL.
    Prioritizes JSON-LD data, falls back to enhanced HTML parsing.
    Returns a dictionary of wine data or None if scraping fails.
    """
    logger.debug(f"Starting Vivino data scrape for URL: {vivino_url}")
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', # Desktop user agent (seems more reliable for Vivino)
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    ]
    headers = {
        'User-Agent': user_agents[0] # Use a desktop user agent by default
    }

    wine_data = {
        'vivino_url': vivino_url,
        'name': 'Unknown Wine',
        'vintage': None,
        'varietal': 'Unknown Varietal',
        'region': 'Unknown Region',
        'country': 'Unknown Country',
        'vivino_rating': None,
        'vivino_num_ratings': None,
        'price_usd': None,
        'image_url': None,
        # Quantity is managed by the inventory system, not scraped
    }

    # Master list to collect all grape names found from any source (JSON-LD or HTML)
    all_grape_names_collected = []

    try:
        response = requests.get(vivino_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # --- Attempt to extract data from JSON-LD first (most reliable) ---
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                json_ld = json.loads(script.string)

                if isinstance(json_ld, dict):
                    # Product Schema (most common for wine pages)
                    if json_ld.get('@type') == 'Product':
                        if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld:
                            wine_data['name'] = json_ld['name'].strip()

                        if wine_data['image_url'] is None and 'image' in json_ld:
                            if isinstance(json_ld['image'], list) and json_ld['image']:
                                wine_data['image_url'] = json_ld['image'][0]
                            elif isinstance(json_ld['image'], str):
                                wine_data['image_url'] = json_ld['image']

                        offers = json_ld.get('offers')
                        if wine_data['price_usd'] is None and offers:
                            if isinstance(offers, dict) and offers.get('@type') == 'Offer':
                                price_str = offers.get('price')
                                price_currency = offers.get('priceCurrency')
                                if price_str and price_currency == 'USD':
                                    try: wine_data['price_usd'] = float(price_str);
                                    except ValueError: pass
                            elif isinstance(offers, list):
                                for offer in offers:
                                    if isinstance(offer, dict) and offer.get('@type') == 'Offer':
                                        price_str = offer.get('price')
                                        price_currency = offer.get('priceCurrency')
                                        if price_str and price_currency == 'USD':
                                            try: wine_data['price_usd'] = float(price_str); break
                                            except ValueError: pass

                        aggregate_rating = json_ld.get('aggregateRating')
                        if aggregate_rating and isinstance(aggregate_rating, dict):
                            if wine_data['vivino_rating'] is None:
                                rating_value = aggregate_rating.get('ratingValue')
                                if rating_value is not None:
                                    try: wine_data['vivino_rating'] = float(str(rating_value).replace(',', '.'));
                                    except ValueError: pass
                            if wine_data['vivino_num_ratings'] is None:
                                review_count = aggregate_rating.get('reviewCount')
                                if review_count is not None:
                                    try: wine_data['vivino_num_ratings'] = int(str(review_count).replace(',', ''));
                                    except ValueError: pass

                        contains_wine = json_ld.get('containsWine')
                        if contains_wine and isinstance(contains_wine, dict) and contains_wine.get('@type') == 'Wine':
                            if wine_data['vintage'] is None and 'vintage' in contains_wine:
                                try: wine_data['vintage'] = int(contains_wine['vintage']);
                                except ValueError: pass

                            grapes = contains_wine.get('grape')
                            if grapes: # Check for existence
                                if isinstance(grapes, list):
                                    grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                    if grape_names:
                                        all_grape_names_collected.extend(grape_names)
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
                                                if wine_data['country'] == 'Unknown Country' and '/countries/' in item['url']:
                                                    wine_data['country'] = item['name'].strip()
                                                if wine_data['region'] == 'Unknown Region' and '/regions/' in item['url']:
                                                    wine_data['region'] = item['name'].strip()

                    elif json_ld.get('@type') == 'WebPage':
                        content_location = json_ld.get('contentLocation')
                        if content_location and isinstance(content_location, dict):
                            if wine_data['region'] == 'Unknown Region' and 'name' in content_location:
                                wine_data['region'] = content_location['name'].strip()
                            if wine_data['country'] == 'Unknown Country' and 'address' in content_location and isinstance(content_location['address'], dict):
                                if 'addressCountry' in content_location['address']:
                                    wine_data['country'] = content_location['address']['addressCountry'].strip()

                    elif json_ld.get('@type') == 'Wine':
                        if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld:
                            wine_data['name'] = json_ld['name'].strip()
                        if wine_data['vintage'] is None and 'vintage' in json_ld:
                            try: wine_data['vintage'] = int(json_ld['vintage']);
                            except ValueError: pass
                        if 'grape' in json_ld:
                            grapes = json_ld['grape']
                            if grapes: # Check for existence
                                if isinstance(grapes, list) and grapes:
                                    grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                    if grape_names:
                                        all_grape_names_collected.extend(grape_names)
                                elif isinstance(grapes, dict) and 'name' in grapes:
                                    all_grape_names_collected.append(grapes['name'].strip())
                        if wine_data['region'] == 'Unknown Region' and 'region' in json_ld:
                            region_info = json_ld['region']
                            if isinstance(region_info, dict) and 'name' in region_info:
                                wine_data['region'] = region_info['name'].strip()
                        if wine_data['country'] == 'Unknown Country' and 'country' in json_ld:
                            country_info = json_ld['country']
                            if isinstance(country_info, dict) and 'name' in country_info:
                                wine_data['country'] = country_info['name'].strip()
                        if wine_data['image_url'] is None and 'image' in json_ld:
                            if isinstance(json_ld['image'], list) and json_ld['image']:
                                wine_data['image_url'] = json_ld['image'][0]
                            elif isinstance(json_ld['image'], str):
                                wine_data['image_url'] = json_ld['image']

            except (json.JSONDecodeError, KeyError, TypeError) as json_err:
                logger.debug(f"Vivino JSON-LD parsing error (may be benign if other schemas exist): {json_err}")
                pass

        # --- Fallback to HTML parsing for any remaining missing data from Vivino ---
        if wine_data['name'] == 'Unknown Wine':
            name_tag = soup.find('h1', class_='wine-page-header__name')
            if name_tag:
                wine_data['name'] = " ".join(name_tag.text.strip().split())
                logger.debug(f"HTML Name found: '{wine_data['name']}'")

        # Get vintage (from name, or specific elements)
        if wine_data['vintage'] is None and wine_data['name'] and 'Unknown Wine' not in wine_data['name']:
            name_vintage_match = re.search(r'\b(19\d{2}|20\d{2})\b', wine_data['name'])
            if name_vintage_match:
                try:
                    year = int(name_vintage_match.group(0))
                    current_year = 2025 # Assuming current year for vintage validation
                    if 1900 <= year <= current_year + 5: # Allow a few years into the future for new releases
                        wine_data['vintage'] = year
                        cleaned_name = wine_data['name'].replace(name_vintage_match.group(0), '').strip()
                        wine_data['name'] = " ".join(cleaned_name.split())
                        logger.debug(f"HTML Vintage (name text) found and removed from name: {wine_data['vintage']}, Cleaned Name: '{wine_data['name']}'")
                except ValueError:
                    pass

        if wine_data['vintage'] is None:
            vintage_span = soup.find('span', class_='vintage')
            if vintage_span:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', vintage_span.text.strip())
                if year_match:
                    try:
                        wine_data['vintage'] = int(year_match.group(0))
                        logger.debug(f"HTML Vintage (span.vintage) found: {wine_data['vintage']}")
                    except ValueError: pass

        logger.debug(f"Vintage scraping complete. Current data: {wine_data['vintage']}")

        # --- NEW & IMPROVED: Get Varietal, Region, and Country from direct links ---
        all_relevant_links = soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/'))
        logger.debug(f"Attempting to find country/region/varietal from all relevant links. Found {len(all_relevant_links)} links.")

        for link in all_relevant_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            if '/wine-countries/' in href and wine_data['country'] == 'Unknown Country':
                wine_data['country'] = text
                logger.debug(f"HTML Country (direct link) found: {wine_data['country']} from href: {href}")
            elif '/wine-regions/' in href and wine_data['region'] == 'Unknown Region':
                wine_data['region'] = text
                logger.debug(f"HTML Region (direct link) found: {wine_data['region']} from href: {href}")
            elif '/grapes/' in href: # Always try to collect grape names from links
                if text and 'blend' not in text.lower() and 'wine' not in text.lower():
                    all_grape_names_collected.append(text)
                elif text: # Still append if it's a generic 'blend' or 'wine' for later filtering
                    all_grape_names_collected.append(text)


        # Fallback to definition lists if still not found in direct links or JSON-LD for varietal/region/country
        dl_tags = soup.find_all('dl', class_=re.compile(r'wine-facts|product-details'))
        if dl_tags:
            logger.debug(f"Attempting to find country/region/varietal from DL elements. Found {len(dl_tags)} definition lists.")
        for dl in dl_tags:
            dt_dd_pairs = list(zip(dl.find_all('dt'), dl.find_all('dd')))
            for dt, dd in dt_dd_pairs:
                label = dt.get_text(strip=True)
                value = dd.get_text(strip=True)

                if 'Country' in label and wine_data['country'] == 'Unknown Country' and value.strip():
                    wine_data['country'] = value
                    logger.debug(f"HTML Country (DL) found: {wine_data['country']}")
                elif 'Region' in label and wine_data['region'] == 'Unknown Region' and value.strip():
                    wine_data['region'] = value
                    logger.debug(f"HTML Region (DL) found: {wine_data['region']}")
                elif ('Grape' in label or 'Varietal' in label):
                    if value.strip():
                        all_grape_names_collected.append(value.strip())


        # --- FINAL Varietal Assignment (Post-processing all collected grapes) ---
        if all_grape_names_collected:
            # Filter out generic terms, keeping only actual varietal names
            filtered_grapes = [
                g for g in all_grape_names_collected
                if g.lower() not in ['red wine', 'white wine', 'sparkling wine', 'rosé wine', 'dessert wine', 'fortified wine', 'blend']
            ]

            # If after filtering we have specific grapes, use them. Maintain order as much as possible.
            if filtered_grapes:
                # Use a list to maintain order, convert to set for uniqueness, then back to list to preserve (first seen) order.
                seen_grapes = set()
                ordered_unique_grapes = []
                for grape in all_grape_names_collected:  # Iterate through ALL collected, not just filtered
                    cleaned_grape = grape.strip()
                    if cleaned_grape.lower() not in [
                        'red wine', 'white wine', 'sparkling wine', 'rosé wine', 'dessert wine', 'fortified wine', 'blend'
                    ] and cleaned_grape not in seen_grapes:
                        ordered_unique_grapes.append(cleaned_grape)
                        seen_grapes.add(cleaned_grape)

                # --- Apply Bordeaux Region Heuristics for ordering ---
                if 'region' in wine_data and isinstance(wine_data['region'], str):
                    region_str = wine_data['region'].lower()
                    
                    if 'saint-émilion' in region_str or 'pomerol' in region_str or 'fronsac' in region_str or 'canon-fronsac' in region_str:
                        # Right Bank: Prioritize Merlot, then Cabernet Franc, then Cabernet Sauvignon
                        preferred_order = ['Merlot', 'Cabernet Franc', 'Cabernet Sauvignon']
                        
                        reordered_grapes = []
                        for preferred_grape in preferred_order:
                            for g in ordered_unique_grapes:
                                if preferred_grape.lower() == g.lower() and g not in reordered_grapes:
                                    reordered_grapes.append(g)
                        # Add any other grapes that were not in the preferred list
                        for g in ordered_unique_grapes:
                            if g not in reordered_grapes:
                                reordered_grapes.append(g)
                        ordered_unique_grapes = reordered_grapes
                        logger.debug(f"Bordeaux Right Bank heuristic applied. Ordered grapes: {ordered_unique_grapes}")

                    elif any(lb_region in region_str for lb_region in ['médoc', 'pauillac', 'margaux', 'haut-médoc', 'saint-estèphe', 'saint-julien', 'listrac', 'moulis', 'graves']):
                        # Left Bank: Prioritize Cabernet Sauvignon, then Merlot, then Cabernet Franc
                        preferred_order = ['Cabernet Sauvignon', 'Merlot', 'Cabernet Franc']
                        
                        reordered_grapes = []
                        for preferred_grape in preferred_order:
                            for g in ordered_unique_grapes:
                                if preferred_grape.lower() == g.lower() and g not in reordered_grapes:
                                    reordered_grapes.append(g)
                        # Add any other grapes that were not in the preferred list
                        for g in ordered_unique_grapes:
                            if g not in reordered_grapes:
                                reordered_grapes.append(g)
                        ordered_unique_grapes = reordered_grapes
                        logger.debug(f"Bordeaux Left Bank heuristic applied. Ordered grapes: {ordered_unique_grapes}")

                # --- Apply Syrah/Shiraz Renaming Logic ---
                country_for_shiraz_syrah = wine_data.get('country', '').strip().lower()
                is_australia_sa = (country_for_shiraz_syrah == 'australia' or country_for_shiraz_syrah == 'south africa')

                transformed_grapes = []
                for grape in ordered_unique_grapes:
                    if 'syrah' in grape.lower():
                        if is_australia_sa:
                            transformed_grapes.append('Shiraz')
                        else:
                            transformed_grapes.append('Syrah')
                    elif 'shiraz' in grape.lower(): # Also catch if it was already Shiraz but needs to be Syrah
                        if not is_australia_sa:
                            transformed_grapes.append('Syrah')
                        else:
                            transformed_grapes.append('Shiraz')
                    else:
                        transformed_grapes.append(grape)

                wine_data['varietal'] = ", ".join(transformed_grapes)
                logger.debug(f"Final Varietal set from ordered unique collected sources (Syrah/Shiraz logic applied): {wine_data['varietal']}")

            elif 'blend' in [g.lower() for g in all_grape_names_collected]:
                wine_data['varietal'] = 'Blend'
                logger.debug(f"Varietal set to 'Blend' as only generic terms found.")
            else:
                wine_data['varietal'] = 'Unknown Varietal'
                logger.debug(f"All collected varietals were generic. Varietal set to: {wine_data['varietal']}")
        else: # No grape names collected at all
            wine_data['varietal'] = 'Unknown Varietal'
            logger.debug(f"No grape names were collected from any source. Varietal set to: {wine_data['varietal']}")


        logger.debug(f"Region/Country scraping finished HTML attempts. Current data: Region='{wine_data['region']}', Country='{wine_data['country']}'")

        # --- Specific US Country Fallback (truly a last resort now) ---
        if wine_data['country'] == 'Unknown Country' and "/US/en/" in vivino_url:
            wine_data['country'] = "United States"
            logger.debug(f"Country defaulted to 'United States' due to URL pattern (final fallback).")

        # Get Vivino number of ratings
        if wine_data['vivino_num_ratings'] is None:
            ratings_elements_classes = [
                re.compile(r'vivinoRating_ratingsCount__value'),
                re.compile(r'text-micro text-bold mt-2 text-color-gray-600'),
                re.compile(r'vivinoRating_ratings'),
                re.compile(r'vivinoRating_summary__reviewerAndActions'),
                re.compile(r'community-score__total-ratings'),
                re.compile(r'community-score__reviews-count'),
                re.compile(r'review-score__count')
            ]
            for class_name in ratings_elements_classes:
                elem = soup.find(class_=class_name)
                if elem:
                    num_ratings_text = elem.get_text(strip=True)
                    num_ratings_match = re.search(r'([\d,\.]+)\s*(ratings|K|M)?', num_ratings_text, re.IGNORECASE)
                    if num_ratings_match:
                        value_str = num_ratings_match.group(1).replace(',', '.')
                        suffix = (num_ratings_match.group(2) or '').lower()
                        try:
                            value = float(value_str)
                            if suffix == 'k':
                                value *= 1_000
                            elif suffix == 'm':
                                value *= 1_000_000
                            wine_data['vivino_num_ratings'] = int(value)
                            logger.debug(f"HTML Num Ratings ({class_name.pattern}) found: {wine_data['vivino_num_ratings']}")
                            break
                        except ValueError: pass
            if wine_data['vivino_num_ratings'] is None:
                rating_text_matches = re.finditer(r'(\d[\d,\.]*)\s*(global\s*)?ratings', response.text, re.IGNORECASE)
                for match in rating_text_matches:
                    value_str = match.group(1).replace(',', '.')
                    try:
                        wine_data['vivino_num_ratings'] = int(float(value_str))
                        logger.debug(f"HTML Num Ratings (text match) found: {wine_data['vivino_num_ratings']}")
                        break
                    except ValueError: pass
        logger.debug(f"Vivino Num Ratings scraping complete. Current data: {wine_data['vivino_num_ratings']}")

        # Get Vivino rating
        if wine_data['vivino_rating'] is None:
            rating_tags = soup.find_all('div', class_=re.compile(r'vivinoRating_averageValue|average-value|community-score__score|rating-value'))
            for rating_tag in rating_tags:
                try:
                    rating_text = rating_tag.text.strip().replace(',', '.')
                    if rating_text:
                        wine_data['vivino_rating'] = float(rating_text)
                        logger.debug(f"HTML Vivino Rating found: {wine_data['vivino_rating']}")
                        break
                except ValueError: pass
        logger.debug(f"Vivino Rating scraping complete. Current data: {wine_data['vivino_rating']}")

        # Get image URL
        if wine_data['image_url'] is None:
            image_tag = soup.find('img', class_=re.compile(r'wine-page-image__image|vivinoImage_image|image-preview__image|image-container__image'))
            if image_tag:
                if image_tag.has_attr('src') and 'vivino.com' in image_tag['src']:
                    wine_data['image_url'] = image_tag['src']
                    logger.debug(f"HTML Image URL (src) found: {wine_data['image_url']}")
                elif image_tag.has_attr('data-src') and 'vivino.com' in image_tag['data-src']:
                    wine_data['image_url'] = image_tag['data-src']
                    logger.debug(f"HTML Image URL (data-src) found: {wine_data['image_url']}")
                elif image_tag.has_attr('src'): # Generic fallback for any src
                    wine_data['image_url'] = image_tag['src']
                    logger.debug(f"HTML Image URL (generic src) found: {wine_data['image_url']}")
                elif image_tag.has_attr('data-src'): # Generic fallback for any data-src
                    wine_data['image_url'] = image_tag['data-src']
                    logger.debug(f"HTML Image URL (generic data-src) found: {wine_data['image_url']}")
        logger.debug(f"Image URL scraping complete. Current data: {wine_data['image_url']}")

        # Get price
        if wine_data['price_usd'] is None:
            price_tag = soup.find('div', class_=re.compile(r'purchase-block__price|price'))
            if price_tag:
                price_text = price_tag.text.strip()
                price_match = re.search(r'\$?(\d[\d\.,]*)', price_text)
                if price_match:
                    try: wine_data['price_usd'] = float(price_match.group(1).replace(',', ''));
                    except ValueError: pass
        logger.debug(f"Price scraping complete. Current data: {wine_data['price_usd']}")

        # --- Final Fallback Layer: Parse the URL itself ---
        # This runs only if the above methods failed to find the data.
        # 1. Fallback for Vintage from URL query parameter
        if wine_data['vintage'] is None:
            try:
                # Use urllib.parse to get query parameters from vivino_url
                parsed_url = urlparse(vivino_url)
                query_params = parse_qs(parsed_url.query)
                if 'year' in query_params:
                    year_str = query_params['year'][0]
                    wine_data['vintage'] = int(year_str)
                    logger.debug(f"Vintage (URL Fallback) found: {wine_data['vintage']}")
            except (ValueError, IndexError):
                logger.debug("Could not parse vintage from URL query parameter.")
                pass # Ignore errors if 'year' param is not present or invalid

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP/Network error during Vivino scrape for {vivino_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Vivino scrape for {vivino_url}: {e}")
        return None

    logger.info(f"Successfully scraped Vivino data for {wine_data.get('name', 'Unknown')} ({wine_data.get('vintage', 'NV')})")
    return wine_data

# Modified to accept quantity
def insert_wine_data(wine_data, quantity=1):
    """
    Inserts new wine data into the SQLite database or updates the quantity
    if a wine with the same Vivino URL already exists.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if the wine already exists
        cursor.execute("SELECT id, quantity FROM wines WHERE vivino_url = ?", (wine_data['vivino_url'],))
        existing_wine = cursor.fetchone()

        if existing_wine:
            wine_id, current_quantity = existing_wine
            new_quantity = current_quantity + quantity
            cursor.execute('''
                UPDATE wines
                SET quantity = ?,
                    name = ?,
                    vintage = ?,
                    varietal = ?,
                    region = ?,
                    country = ?,
                    vivino_rating = ?,
                    vivino_num_ratings = ?,
                    price_usd = ?,
                    image_url = ?,
                    added_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                new_quantity,
                wine_data['name'],
                wine_data['vintage'],
                wine_data['varietal'],
                wine_data['region'],
                wine_data['country'],
                wine_data['vivino_rating'],
                wine_data['vivino_num_ratings'],
                wine_data['price_usd'],
                wine_data['image_url'],
                wine_id
            ))
            logger.info(f"Updated quantity for '{wine_data['name']}' to {new_quantity}.")
        else:
            # Insert new wine with specified quantity
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, vivino_num_ratings, price_usd, image_url, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wine_data['vivino_url'],
                wine_data['name'],
                wine_data['vintage'],
                wine_data['varietal'],
                wine_data['region'],
                wine_data['country'],
                wine_data['vivino_rating'],
                wine_data['vivino_num_ratings'],
                wine_data['price_usd'],
                wine_data['image_url'],
                quantity # Use the provided quantity for new inserts
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

# --- Flask Routes ---


@app.route('/scan-wine', methods=['POST'])
def scan_wine():
    """
    Endpoint to receive a Vivino URL, scrape wine data, and store/update it in the database.
    Also triggers synchronization with Home Assistant To-Do list.
    """
    data = request.get_json()
    if not data or 'vivino_url' not in data:
        logger.warning("Received invalid data for /scan-wine endpoint: %s", data)
        return jsonify({"status": "error", "message": "Missing 'vivino_url' in request body"}), 400

    vivino_url = data['vivino_url']
    # Get quantity from request, default to 1 if not provided
    quantity = data.get('quantity', 1)
    if not isinstance(quantity, int) or quantity < 1:
        logger.warning(f"Invalid quantity provided: {quantity}. Defaulting to 1.")
        quantity = 1

    logger.info(f"Received request to process Vivino URL: {vivino_url} with quantity: {quantity}")

    wine_data = scrape_vivino_data(vivino_url)
    if wine_data:

        if insert_wine_data(wine_data, quantity):
            # Get the current total quantity from the DB after the insert/update
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT quantity FROM wines WHERE vivino_url = ?", (vivino_url,))
            current_total_quantity_row = cursor.fetchone()
            conn.close()

            current_total_quantity = 0
            if current_total_quantity_row:
                current_total_quantity = current_total_quantity_row[0]

            # Sync with HA To-Do List based on current total quantity
            sync_to_ha_todo(wine_data, current_total_quantity)

            return jsonify({
                "status": "success",
                "message": "Wine data scraped and stored/updated.",
                "wine_name": wine_data['name'],
                "vintage": wine_data['vintage'],
                "vivino_url": wine_data['vivino_url'],
                "quantity_added": quantity, # Confirm the quantity added/incremented
                "current_total_quantity": current_total_quantity # Added for clarity
            }), 200
        else:
            return jsonify({"status": "error", "message": "Failed to store/update wine data in database."}), 500
    else:
        return jsonify({"status": "error", "message": "Failed to scrape data from Vivino URL."}), 500

@app.route('/inventory', methods=['GET'])
def get_inventory():
    """
    Endpoint to retrieve the current wine inventory from the database.
    Supports filtering by name and vintage.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    name_filter = request.args.get('name')
    vintage_filter = request.args.get('vintage')

    query = "SELECT * FROM wines"
    params = []
    conditions = []

    if name_filter:
        conditions.append("name LIKE ?")
        params.append(f"%{name_filter}%")
    if vintage_filter:
        conditions.append("vintage = ?")
        params.append(vintage_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY added_at DESC"

    try:
        cursor.execute(query, params)
        wines = cursor.fetchall()
        conn.close()

        wine_list = []
        for wine_row in wines:
            wine_dict = dict(wine_row)
            wine_list.append(wine_dict)

        logger.info(f"Returning {len(wine_list)} wines from inventory.")
        return jsonify(wine_list), 200
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving inventory: {e}")
        return jsonify({"status": "error", "message": "Database error retrieving inventory."}), 500
    finally:
        conn.close()

@app.route('/inventory/wine/set_quantity', methods=['POST'])
def set_wine_quantity():
    """
    Endpoint to set the quantity of a specific wine in the inventory.
    If quantity is set to 0, the wine is deleted.
    Triggers synchronization with Home Assistant To-Do list.
    """
    data = request.get_json()
    if not data or 'vivino_url' not in data or 'quantity' not in data:
        logger.warning("Received invalid data for /inventory/wine/set_quantity endpoint: %s", data)
        return jsonify({"status": "error", "message": "Missing 'vivino_url' or 'quantity' in request body"}), 400

    vivino_url = data['vivino_url']
    new_quantity = data['quantity']

    if not isinstance(new_quantity, int) or new_quantity < 0:
        return jsonify({"status": "error", "message": "Quantity must be a non-negative integer."}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Fetch existing wine data before update for syncing with HA
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()

        if wine_data_row:
            columns = [description[0] for description in cursor.description]
            wine_data_dict = dict(zip(columns, wine_data_row))

            if new_quantity == 0:
                cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Successfully deleted wine {vivino_url} as quantity was set to 0.")
                    sync_to_ha_todo(wine_data_dict, 0) # Sync with HA to ensure removal
                    return jsonify({"status": "success", "message": "Wine deleted as quantity was set to 0."}), 200
                else:
                    logger.warning(f"Wine {vivino_url} not found for deletion after setting quantity to 0.")
                    return jsonify({"status": "error", "message": "Wine not found for quantity update/deletion."}), 404
            else:
                cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Successfully set quantity for wine {vivino_url} to {new_quantity}.")
                    sync_to_ha_todo(wine_data_dict, new_quantity) # Sync with HA
                    return jsonify({"status": "success", "message": f"Quantity for wine set to {new_quantity}."}), 200
                else:
                    logger.warning(f"No wine found to set quantity for URL: {vivino_url}")
                    return jsonify({"status": "error", "message": "Wine not found for quantity update."}), 404
        else:
            logger.warning(f"No wine found for quantity update for URL: {vivino_url}")
            return jsonify({"status": "error", "message": "Wine not found for quantity update."}), 404

    except sqlite3.Error as e:
        logger.error(f"Database error setting wine quantity: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error setting wine quantity."}), 500
    finally:
        conn.close()

@app.route('/api/consume-wine', methods=['POST'])
def consume_wine_from_webhook():
            """
            Webhook endpoint called by Home Assistant automation when a To-Do item is completed.
            Parses the wine name and vintage from the item, decrements its quantity in the DB,
            and updates the To-Do list.
            """
            try:
                        data = request.get_json()
                        if not data or "item" not in data:
                                    logger.warning("Malformed webhook: missing 'item' field. Received: %s", data)
                                    return jsonify({"status": "error", "message": "Missing 'item' in request body"}), 400

                        item_text = data["item"]
                        logger.info(f"Webhook received for consumed wine: {item_text}")

                        # The item_text from HA will now be "Wine Name (Vintage)" (no 'xN')
                        parsed_name = None
                        parsed_vintage = None

                        # Regex to extract "Name (Vintage)"
                        match = re.match(r'^(.*)\s*\((\d{4})\)$', item_text)
                        if match:
                                    parsed_name = match.group(1).strip()
                                    parsed_vintage = int(match.group(2))
                        else:
                                    logger.warning(f"Failed to parse wine name and vintage from item: '{item_text}'. Expected 'Name (Vintage)' format.")
                                    return jsonify({"status": "error", "message": "Could not parse item name and vintage from To-Do item. Expected 'Name (Vintage)' format."}), 400

                        name = parsed_name
                        vintage = parsed_vintage

                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        try:
                                    # Try exact match
                                    cursor.execute("SELECT quantity, vivino_url FROM wines WHERE name = ? AND vintage = ?", (name, vintage))
                                    result = cursor.fetchone()

                                    if result:
                                                current_db_quantity, vivino_url_for_sync = result
                                                cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url_for_sync,))
                                                wine_data_row_for_sync = cursor.fetchone()
                                                wine_data_dict_for_sync = {}
                                                if wine_data_row_for_sync:
                                                            columns = [description[0] for description in cursor.description]
                                                            wine_data_dict_for_sync = dict(zip(columns, wine_data_row_for_sync))

                                                if current_db_quantity > 0:
                                                            new_quantity = current_db_quantity - 1
                                                            if new_quantity == 0:
                                                                        cursor.execute("DELETE FROM wines WHERE name = ? AND vintage = ?", (name, vintage))
                                                                        conn.commit()
                                                                        logger.info(f"Deleted wine '{name} ({vintage})' as quantity reached 0.")
                                                                        sync_to_ha_todo(wine_data_dict_for_sync, 0)
                                                                        return jsonify({"status": "success", "message": f"Wine consumed and deleted. New quantity: {new_quantity}."}), 200
                                                            else:
                                                                        cursor.execute("UPDATE wines SET quantity = ? WHERE name = ? AND vintage = ?", (new_quantity, name, vintage))
                                                                        conn.commit()
                                                                        logger.info(f"Decremented quantity for '{name} ({vintage})' to {new_quantity}")
                                                                        sync_to_ha_todo(wine_data_dict_for_sync, new_quantity)
                                                                        return jsonify({"status": "success", "message": f"Quantity updated. New quantity: {new_quantity}."}), 200
                                                else:
                                                            logger.warning(f"Quantity already 0 for '{name} ({vintage})'. No decrement performed.")
                                                            return jsonify({"status": "warning", "message": "Quantity already zero. No action taken."}), 404

                                    # No match found — try to rename an "Unknown Wine"
                                    cursor.execute("SELECT id, quantity FROM wines WHERE name = ? AND vintage = ?", ('Unknown Wine', vintage))
                                    unknown_matches = cursor.fetchall()
                                    if len(unknown_matches) == 1:
                                                wine_id, quantity = unknown_matches[0]
                                                cursor.execute("UPDATE wines SET name = ? WHERE id = ?", (name, wine_id))
                                                conn.commit()
                                                logger.info(f"Renamed wine in DB from 'Unknown Wine ({vintage})' to '{name} ({vintage})'")

                                                # Re-sync updated wine to HA To-Do list
                                                cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
                                                updated_row = cursor.fetchone()
                                                if updated_row:
                                                            columns = [description[0] for description in cursor.description]
                                                            wine_dict = dict(zip(columns, updated_row))
                                                            sync_to_ha_todo(wine_dict, wine_dict.get("quantity", 1))

                                                return jsonify({"status": "success", "message": f"Renamed unknown wine to '{name}' without changing quantity."}), 200

                                    logger.warning(f"No matching wine found in DB for '{name} ({vintage})'.")
                                    return jsonify({"status": "warning", "message": "No matching wine found in inventory."}), 404
                        except sqlite3.Error as e:
                                    logger.error(f"Database error consuming wine: {e}")
                                    conn.rollback()
                                    return jsonify({"status": "error", "message": "Database error consuming wine."}), 500
                        finally:
                                    conn.close()
            except Exception as e:
                        logger.error(f"Error processing webhook for consumed wine: {e}", exc_info=True)
                        return jsonify({"status": "error", "message": f"Internal server error processing webhook: {e}"}), 500


@app.route('/inventory/wine/consume', methods=['POST'])
def consume_wine():
    """
    Endpoint for the frontend to consume (decrement quantity) a wine by its Vivino URL.
    Triggers synchronization with Home Assistant To-Do list.
    """
    data = request.get_json()
    vivino_url = data.get('vivino_url')

    if not vivino_url:
        return jsonify({'error': 'vivino_url is required'}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Fetch the current wine data to pass to sync_to_ha_todo later
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_data_row = cursor.fetchone()

        if not wine_data_row:
            logger.warning(f"Wine not found for consumption: {vivino_url}")
            return jsonify({'error': 'Wine not found in inventory'}), 404

        columns = [description[0] for description in cursor.description]
        wine_data_dict = dict(zip(columns, wine_data_row))

        current_quantity = wine_data_dict['quantity']
        wine_id = wine_data_dict['id']

        new_quantity = 0

        if current_quantity > 1:
            new_quantity = current_quantity - 1
            cursor.execute("UPDATE wines SET quantity = ?, added_at = CURRENT_TIMESTAMP WHERE id = ?", (new_quantity, wine_id))
            logger.info(f"Decremented quantity for wine {vivino_url} to {new_quantity}.")
            sync_to_ha_todo(wine_data_dict, new_quantity)
        else: # Quantity is 1, so it becomes 0 after decrement (delete)
            new_quantity = 0
            cursor.execute("DELETE FROM wines WHERE id = ?", (wine_id,))
            logger.info(f"Successfully consumed and deleted wine {vivino_url} as quantity reached 0.")
            sync_to_ha_todo(wine_data_dict, new_quantity)

        conn.commit()
        return jsonify({'status': 'success', 'new_quantity': new_quantity})
    except sqlite3.Error as e:
        logger.error(f"Database error during consumption: {e}")
        conn.rollback()
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()


@app.route('/inventory/wine', methods=['DELETE'])
def delete_wine():
    """
    Endpoint to delete a wine from the inventory by its Vivino URL.
    Triggers synchronization with Home Assistant To-Do list to remove the item.
    """
    data = request.get_json()
    if not data or 'vivino_url' not in data:
        logger.warning("Received invalid data for /inventory/wine DELETE endpoint: %s", data)
        return jsonify({"status": "error", "message": "Missing 'vivino_url' in request body"}), 400

    vivino_url = data['vivino_url']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Before deleting, get wine data to remove from HA To-Do
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
        wine_to_delete = cursor.fetchone()

        wine_columns_description = None
        if wine_to_delete:
            wine_columns_description = cursor.description

        cursor.execute("DELETE FROM wines WHERE vivino_url = ?", (vivino_url,))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Successfully deleted wine with URL: {vivino_url}")

            if wine_to_delete and wine_columns_description:
                columns = [description[0] for description in wine_columns_description]
                wine_data_dict = dict(zip(columns, wine_to_delete))
                sync_to_ha_todo(wine_data_dict, 0) # Call with quantity 0 to ensure removal from HA

            return jsonify({"status": "success", "message": "Wine deleted successfully."}), 200
        else:
            logger.warning(f"No wine found to delete for URL: {vivino_url}")
            return jsonify({"status": "error", "message": "Wine not found for deletion."}), 404
    except sqlite3.Error as e:
        logger.error(f"Database error deleting wine: {e}")
        conn.rollback()
        return jsonify({"status": "error", "message": "Database error deleting wine."}), 500
    finally:
        conn.close()

@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha():
    """
    Endpoint to trigger a full synchronization of all wines from the database
    to the Home Assistant To-Do list.
    """
    logger.info("Received request to sync all wines to Home Assistant.")
    try:
        # clear_ha_todo_list() # Commented out due to persistent 400 Bad Request and API limitations
        sync_db_to_ha_todo() # Then re-add/update all wines from DB
        return jsonify({"status": "success", "message": "All wines synchronized to Home Assistant."}), 200
    except Exception as e:
        logger.error(f"Error during full synchronization to Home Assistant: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    """
    Endpoint to reinitialize the database from the web UI.
    This will delete all existing wine data.
    """
    logger.warning("Received request to reinitialize database from web UI.")
    try:
        reinitialize_database()
        return jsonify({"status": "success", "message": "Database reinitialized successfully. Please restart add-on from Home Assistant if needed."}), 200
    except Exception as e:
        logger.error(f"Error reinitializing database from web UI: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def serve_frontend():
    """Serves the main frontend HTML file."""
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    """Serves static files (CSS, JS, images) from the 'frontend' directory."""
    return send_from_directory("frontend", path)


# Application Entry Point and Initialization
if __name__ == '__main__':
    # --- Database Initialization / Reinitialization ---
    # Check if REINITIALIZE_DATABASE environment variable is set to trigger a fresh start
    reinitialize_flag = os.environ.get("REINITIALIZE_DATABASE", "false").lower()

    logger.debug(f"DEBUG: REINITIALIZE_DATABASE as read by app: '{reinitialize_flag}' (Type: {type(reinitialize_flag)})")

    # Log the HOME_ASSISTANT_URL being used by the Flask app
    logger.info(f"Flask app using HOME_ASSISTANT_URL: '{HOME_ASSISTANT_URL}'")

    if __name__ == '__main__':
        # --- Database Initialization ---
        logger.info("Ensuring database tables exist.")
        init_db() # Call your existing init_db function

    logger.info("Flask app starting on port 5000...")
    app.run(host='0.0.0.0', port=5000)