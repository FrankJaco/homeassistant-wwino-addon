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

                        aggregate_rating = json_ld.get('aggregateRating')
                        if aggregate_rating and isinstance(aggregate_rating, dict):
                            if wine_data['vivino_rating'] is None:
                                rating_value = aggregate_rating.get('ratingValue')
                                if rating_value is not None:
                                    try:
                                        wine_data['vivino_rating'] = float(str(rating_value).replace(',', '.'));
                                    except ValueError:
                                        pass
                            if wine_data['vivino_num_ratings'] is None:
                                review_count = aggregate_rating.get('reviewCount')
                                if review_count is not None:
                                    try:
                                        wine_data['vivino_num_ratings'] = int(str(review_count).replace(',', ''));
                                    except ValueError:
                                        pass

                        contains_wine = json_ld.get('containsWine')
                        if contains_wine and isinstance(contains_wine, dict) and contains_wine.get('@type') == 'Wine':
                            if wine_data['vintage'] is None and 'vintage' in contains_wine:
                                try:
                                    wine_data['vintage'] = int(contains_wine['vintage']);
                                except ValueError:
                                    pass
                            
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
                            try:
                                wine_data['vintage'] = int(json_ld['vintage']);
                            except ValueError:
                                pass
                        
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
                pass # Continue to the next script tag

        # --- HTML Fallback Logic ---
        # Get image URL - NEW, TARGETED METHOD FIRST
        if wine_data['image_url'] is None:
            # Find all <link rel="preload" as="image"> tags
            preload_links = soup.find_all('link', rel='preload', attrs={'as': 'image'})
            best_image_url = None
            if preload_links:
                for link in preload_links:
                    # Prefer the imagesrcset for higher resolution
                    if 'imagesrcset' in link.attrs:
                        # Extract the first URL from the srcset attribute
                        srcset_urls = link.attrs['imagesrcset'].split(',')
                        if srcset_urls:
                            best_image_url = srcset_urls[0].strip().split(' ')[0]
                            break # Found a good one, no need to continue
                    # Fallback to href if no srcset is available
                    elif 'href' in link.attrs:
                        best_image_url = link.attrs['href']
                        break # Found a good one, no need to continue
            if best_image_url:
                wine_data['image_url'] = best_image_url

        # Check for another image source if still not found
        if wine_data['image_url'] is None:
            # Try to find a div with a specific class that contains the image
            image_div = soup.find('div', class_='wine-hero__image')
            if image_div:
                img_tag = image_div.find('img', class_='background-image')
                if img_tag and 'src' in img_tag.attrs:
                    wine_data['image_url'] = img_tag['src']
        
        # Get Name - Fallback if not found in JSON-LD
        if wine_data['name'] == 'Unknown Wine':
            name_elem = soup.find('h1', class_='vintage-title') or soup.find('h1', class_='wine-name')
            if name_elem:
                name_text = name_elem.get_text(strip=True)
                # Use a regex to separate name and vintage if they are in the same tag
                match = re.search(r'^(.*?)(\s+\d{4})$', name_text)
                if match:
                    wine_data['name'] = match.group(1).strip()
                    if wine_data['vintage'] is None:
                        try:
                            wine_data['vintage'] = int(match.group(2).strip())
                        except ValueError:
                            pass
                else:
                    wine_data['name'] = name_text
        
        # Get Vintage - Fallback if not found in JSON-LD
        if wine_data['vintage'] is None:
            vintage_elem = soup.find('span', class_='vintage')
            if vintage_elem:
                try:
                    wine_data['vintage'] = int(vintage_elem.get_text(strip=True))
                except (ValueError, TypeError):
                    pass # Keep vintage as None
        
        # Get Varietal - Fallback if not found in JSON-LD
        if wine_data['varietal'] == 'Unknown Varietal':
            # Check for varietals within the breadcrumbs (common on vivino)
            varietal_container = soup.find('a', href=lambda href: href and '/grape/' in href)
            if varietal_container:
                # Find all breadcrumb items that are grapes
                grape_links = soup.select('ul.breadcrumb li a[href*="/grape/"]')
                if grape_links:
                    grape_names = [link.get_text(strip=True) for link in grape_links]
                    if grape_names:
                        all_grape_names_collected.extend(grape_names)

            # Check for varietals in the 'Wine style' section (a table or list)
            wine_style_header = soup.find('h3', string=lambda text: text and 'Wine style' in text)
            if wine_style_header:
                style_container = wine_style_header.find_next_sibling('div')
                if style_container:
                    # Look for varietal links or text within this section
                    varietal_links = style_container.select('a[href*="/grape/"]')
                    if varietal_links:
                        grape_names = [link.get_text(strip=True) for link in varietal_links]
                        if grape_names:
                             all_grape_names_collected.extend(grape_names)

        # Process all collected grape names to remove duplicates and join them
        if all_grape_names_collected:
            unique_grapes = sorted(list(set(g.strip() for g in all_grape_names_collected)))
            wine_data['varietal'] = ", ".join(unique_grapes)
            logger.debug(f"Scraped varietals from multiple sources: {wine_data['varietal']}")

        # Get Region and Country - Fallback if not found in JSON-LD
        if wine_data['region'] == 'Unknown Region' or wine_data['country'] == 'Unknown Country':
            # Look for the breadcrumbs, they often contain region and country
            breadcrumb_items = soup.select('ul.breadcrumb li a span')
            for item in breadcrumb_items:
                text = item.get_text(strip=True)
                parent_link = item.find_parent('a')
                if parent_link:
                    href = parent_link.get('href')
                    if href and '/countries/' in href:
                        wine_data['country'] = text
                    elif href and '/regions/' in href:
                        wine_data['region'] = text
                        
        # Get Rating and Number of Ratings - Fallback if not found in JSON-LD
        if wine_data['vivino_rating'] is None:
            rating_elem = soup.find('div', class_='average-rating')
            if rating_elem:
                try:
                    wine_data['vivino_rating'] = float(rating_elem.get_text(strip=True))
                except (ValueError, TypeError):
                    pass # Keep as None
        
        if wine_data['vivino_num_ratings'] is None:
            num_ratings_elem = soup.find('div', class_='rating-count')
            if num_ratings_elem:
                try:
                    ratings_text = num_ratings_elem.get_text(strip=True).replace(' ratings', '').replace(',', '')
                    wine_data['vivino_num_ratings'] = int(ratings_text)
                except (ValueError, TypeError):
                    pass # Keep as None


        logger.debug(f"Finished scraping Vivino data: {wine_data}")
        return wine_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to scrape Vivino URL {vivino_url}: {e}")
        return None


# --- Flask Routes ---
@app.route("/")
def index():
    """Serves the main HTML page."""
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/wines", methods=["GET"])
def get_all_wines():
    """Fetches all wines from the database and returns them as a JSON list."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wines")
        wines = [dict(row) for row in cursor.fetchall()]
        return jsonify({"wines": wines})
    except sqlite3.Error as e:
        logger.error(f"Database error during get_all_wines: {e}")
        return jsonify({"error": "Database error"}), 500
    finally:
        if conn:
            conn.close()

@app.route("/api/add_wine_vivino", methods=["POST"])
def add_wine_vivino():
    """
    Scrapes a Vivino URL, adds the wine to the database, and returns the added wine data.
    If the wine already exists, it updates the quantity.
    """
    data = request.get_json()
    vivino_url = data.get("vivino_url")
    quantity_to_add = data.get("quantity", 1)

    if not vivino_url:
        return jsonify({"error": "Vivino URL is required"}), 400

    wine_data = scrape_vivino_data(vivino_url)

    if not wine_data:
        return jsonify({"error": "Failed to scrape wine data from Vivino URL"}), 500
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if a wine with the same Vivino URL already exists
        cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (wine_data['vivino_url'],))
        existing_wine = cursor.fetchone()

        if existing_wine:
            # Wine exists, update quantity
            new_quantity = existing_wine['quantity'] + int(quantity_to_add)
            cursor.execute("UPDATE wines SET quantity = ? WHERE vivino_url = ?", (new_quantity, vivino_url))
            conn.commit()
            logger.info(f"Updated quantity for existing wine: {wine_data['name']}. New quantity: {new_quantity}")
            
            # Fetch the updated wine to pass to the sync function
            cursor.execute("SELECT * FROM wines WHERE vivino_url = ?", (vivino_url,))
            updated_wine = cursor.fetchone()
            if updated_wine:
                sync_to_ha_todo(dict(updated_wine), new_quantity)
                return jsonify({"message": f"Updated quantity for '{wine_data['name']}'. New quantity: {new_quantity}"})
            else:
                return jsonify({"error": "Failed to fetch updated wine data"}), 500
        else:
            # Wine does not exist, insert new wine
            cursor.execute('''
                INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, vivino_rating, vivino_num_ratings, image_url, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                wine_data['vivino_url'],
                wine_data['name'],
                wine_data['vintage'],
                wine_data['varietal'],
                wine_data['region'],
                wine_data['country'],
                wine_data['vivino_rating'],
                wine_data['vivino_num_ratings'],
                wine_data['image_url'],
                quantity_to_add
            ))
            conn.commit()
            logger.info(f"Added new wine from Vivino: {wine_data['name']} (Vintage: {wine_data['vintage']})")
            
            # Fetch the new wine to pass to the sync function
            newly_added_id = cursor.lastrowid
            cursor.execute("SELECT * FROM wines WHERE id = ?", (newly_added_id,))
            newly_added_wine = cursor.fetchone()
            if newly_added_wine:
                sync_to_ha_todo(dict(newly_added_wine), int(quantity_to_add))
                return jsonify({"message": f"Successfully added '{wine_data['name']}' to your inventory."})
            else:
                return jsonify({"error": "Failed to fetch newly added wine data"}), 500

    except sqlite3.Error as e:
        logger.error(f"Database error during add_wine_vivino: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error during add_wine_vivino: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    finally:
        if conn:
            conn.close()

@app.route("/api/add_manual_wine", methods=["POST"])
def add_manual_wine():
    """
    Adds a wine from a manual form submission to the database.
    Assigns a unique vivino_url using a timestamp for manual entries.
    """
    data = request.get_json()
    name = data.get("name")
    vintage = data.get("vintage")
    varietal = data.get("varietal")
    region = data.get("region")
    country = data.get("country")
    quantity = data.get("quantity")

    if not name or not quantity:
        return jsonify({"error": "Wine name and quantity are required."}), 400

    # Create a unique vivino_url for manual entries to satisfy the UNIQUE constraint
    unique_vivino_url = f"manual:{int(time.time() * 1000)}"

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO wines (vivino_url, name, vintage, varietal, region, country, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            unique_vivino_url,
            name,
            vintage,
            varietal,
            region,
            country,
            quantity
        ))
        conn.commit()
        logger.info(f"Manually added new wine: {name} (Vintage: {vintage})")

        newly_added_id = cursor.lastrowid
        cursor.execute("SELECT * FROM wines WHERE id = ?", (newly_added_id,))
        newly_added_wine = cursor.fetchone()
        if newly_added_wine:
            sync_to_ha_todo(dict(newly_added_wine), int(quantity))
            return jsonify({"message": f"Successfully added '{name}' manually to your inventory."})
        else:
            return jsonify({"error": "Failed to retrieve newly added wine."}), 500

    except sqlite3.Error as e:
        logger.error(f"Database error during add_manual_wine: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error during add_manual_wine: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/update_quantity", methods=["POST"])
def update_quantity():
    """
    Updates the quantity of a wine in the database.
    """
    data = request.get_json()
    wine_id = data.get("id")
    new_quantity = data.get("quantity")

    if wine_id is None or new_quantity is None:
        return jsonify({"error": "Wine ID and quantity are required"}), 400

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if the wine exists before updating
        cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
        existing_wine = cursor.fetchone()
        if not existing_wine:
            return jsonify({"error": "Wine not found"}), 404

        cursor.execute("UPDATE wines SET quantity = ? WHERE id = ?", (new_quantity, wine_id))
        conn.commit()
        logger.info(f"Updated quantity for wine ID {wine_id} to {new_quantity}")
        
        # Fetch the updated wine to sync
        cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
        updated_wine = cursor.fetchone()
        if updated_wine:
            sync_to_ha_todo(dict(updated_wine), new_quantity)
            return jsonify({"message": "Quantity updated successfully"})
        else:
            return jsonify({"error": "Failed to retrieve updated wine."}), 500
            
    except sqlite3.Error as e:
        logger.error(f"Database error during update_quantity: {e}")
        return jsonify({"error": "Database error"}), 500
    finally:
        if conn:
            conn.close()

@app.route("/api/delete_wine", methods=["POST"])
def delete_wine():
    """
    Deletes a wine from the database.
    """
    data = request.get_json()
    wine_id = data.get("id")

    if wine_id is None:
        return jsonify({"error": "Wine ID is required"}), 400

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Fetch the wine to get its details before deleting for the HA sync
        cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
        wine_to_delete = cursor.fetchone()
        
        if not wine_to_delete:
            return jsonify({"error": "Wine not found"}), 404
        
        # Delete the wine
        cursor.execute("DELETE FROM wines WHERE id = ?", (wine_id,))
        conn.commit()
        logger.info(f"Deleted wine with ID {wine_id}")
        
        # Synchronize with HA To-Do list, passing a quantity of 0 to signal removal
        sync_to_ha_todo(dict(wine_to_delete), 0)
        
        return jsonify({"message": "Wine deleted successfully"})
    except sqlite3.Error as e:
        logger.error(f"Database error during delete_wine: {e}")
        return jsonify({"error": "Database error"}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/reinitialize", methods=["POST"])
def reinitialize():
    """
    Reinitializes the database, deleting all existing data.
    """
    try:
        clear_ha_todo_list()
        reinitialize_database()
        return jsonify({"message": "Database successfully reinitialized. All data has been deleted."}), 200
    except Exception as e:
        logger.error(f"Failed to reinitialize the database: {e}")
        return jsonify({"error": f"Failed to reinitialize the database: {e}"}), 500

# Call the init_db function when the application starts
init_db()

# Sync the local DB to HA To-Do list on startup
sync_db_to_ha_todo()


# Main entry point for the Flask app.
# If you are running this with a simple `flask run` command in development,
# this block will execute. In a production environment like a Home Assistant
# addon, the WSGI server (like Gunicorn) will handle the startup, but this
# is useful for local testing.
if __name__ == "__main__":
    # In a production HA addon, Gunicorn is used.
    # This block is for local development with `python WW-main.py`.
    # To test locally, you will need to set the environment variables:
    # `HOME_ASSISTANT_URL`, `HA_LONG_LIVED_TOKEN`, `TODO_LIST_ENTITY_ID`
    # You may also want to set `DB_PATH` to a local file.
    app.run(host="0.0.0.0", port=5000, debug=True)