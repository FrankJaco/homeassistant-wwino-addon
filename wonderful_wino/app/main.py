import os
import logging
import atexit # <-- NEW IMPORT
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from . import config, db, ha_service, scraper, formatting
import re
from urllib.parse import urlparse, urlunparse, parse_qs
import yaml

# Quieten down the very verbose output from underlying libraries
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('paho.mqtt.client').setLevel(logging.INFO) # Quieten MQTT debug logs

# Configure the root logger for the application
# (config.py already does this, but good to have a fallback)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

# Define the path to the grapes.yaml file
GRAPES_YAML_PATH = os.path.join(os.path.dirname(__file__), 'data', 'grapes.yaml')

# Function to load the grape varietals
def _load_grape_varietals():
    """Loads the grape varietals list from the YAML file."""
    try:
        with open(GRAPES_YAML_PATH, 'r') as f:
            data = yaml.safe_load(f)
            # We assume the YAML is structured as: {'grapes': ['Grape 1', 'Grape 2', ...]}
            varietals = data.get('grapes', [])
            # Convert all varietal names to lowercase for case-insensitive matching later
            return [v.lower() for v in varietals]
    except FileNotFoundError:
        logger.error(f"Grape varietals file not found at: {GRAPES_YAML_PATH}")
        return []
    except Exception as e:
        logger.error(f"Error loading grape varietals from YAML: {e}", exc_info=True)
        return []

# Load the grape varietals on application start
GRAPE_VARIETALS = _load_grape_varietals()
logger.info(f"Loaded {len(GRAPE_VARIETALS)} grape varietals for reference.")
scraper.initialize_varietals(GRAPE_VARIETALS)

# Define the path to the regions.yaml file
REGIONS_YAML_PATH = os.path.join(os.path.dirname(__file__), 'data', 'regions.yaml')

def _load_regions():
    """Loads the regions data from the YAML file."""
    try:
        with open(REGIONS_YAML_PATH, 'r') as f:
            data = yaml.safe_load(f)
            # The YAML is expected to be structured as {Country: {Region: [Subregions...]}}
            return data or {}
    except FileNotFoundError:
        logger.error(f"Regions file not found at: {REGIONS_YAML_PATH}")
        return {}
    except Exception as e:
        logger.error(f"Error loading regions from YAML: {e}", exc_info=True)
        return {}

# Load the regions on application start
REGION_DATA = _load_regions()
logger.info(f"Loaded {len(REGION_DATA)} countries with region data for reference.")

# initialize the scraper with region data
if hasattr(scraper, "initialize_regions"):
    scraper.initialize_regions(REGION_DATA)
# pass to formatter too
if hasattr(formatting, "initialize_regions"):
    formatting.initialize_regions(REGION_DATA)
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

# --- Flask Routes (NO CHANGES TO ROUTES) ---

@app.route('/api/wine/focal-point', methods=['POST'])
def update_focal_point():
    """Updates the focal point for a wine's image."""
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    focal_point = data.get('focal_point')

    if not all([vivino_url, focal_point]):
        return jsonify({"status": "error", "message": "Missing required data."}), 400

    if db.update_image_focal_point(vivino_url, focal_point):
        return jsonify({"status": "success", "message": "Focal point updated."}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found or DB error."}), 404

# --- NEW ROUTE ---
@app.route('/api/log/update', methods=['POST'])
def update_log_entry():
    """Updates the date of a single consumption log entry."""
    data = request.get_json()
    log_id = data.get('log_id')
    new_date = data.get('new_date')

    if not log_id or not new_date:
        return jsonify({"status": "error", "message": "Missing log_id or new_date"}), 400
    
    try:
        # Client should send a full ISO 8601 string, which SQLite will store.
        if db.update_consumption_date(log_id, new_date):
            return jsonify({"status": "success", "message": "Log entry updated."}), 200
        else:
            return jsonify({"status": "error", "message": "Log entry not found or DB error."}), 404
    except Exception as e:
        logger.error(f"Error updating log entry: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An internal error occurred."}), 500


@app.route('/api/wine/history')
def get_wine_history():
    vivino_url = request.args.get('vivino_url')
    if not vivino_url:
        return jsonify({"error": "Missing vivino_url parameter"}), 400
    
    wine = db.get_wine_by_url(vivino_url)
    if not wine:
        return jsonify({"error": "Wine not found"}), 404
    
    history = db.get_consumption_history(wine['id'])
    return jsonify(history), 200

@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings_dict = db.get_settings()
    return jsonify(settings_dict), 200

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid data format"}), 400
    if db.update_settings(data):
        return jsonify({"status": "success", "message": "Settings updated successfully."}), 200
    else:
        return jsonify({"error": "Database error"}), 500

@app.route('/scan-wine', methods=['POST'])
def scan_wine():
    data = request.get_json()
    if not data or 'vivino_url' not in data:
        return jsonify({"status": "error", "message": "Missing 'vivino_url' in request body"}), 400

    original_vivino_url = data['vivino_url']
    quantity = data.get('quantity', 1)
    cost_tier = data.get('cost_tier')
    manual_vintage_str = data.get('vintage') 
    
    url_for_scraper = original_vivino_url
    if 'utm_source=app' in original_vivino_url:
        logger.info(f"App-sourced URL detected. Sanitizing for scraper: '{original_vivino_url}'")
        parsed_url = urlparse(original_vivino_url)
        
        query_params = parse_qs(parsed_url.query)
        vintage_from_url = query_params.get('year', [None])[0]

        sanitized_parts = parsed_url._replace(query='')
        sanitized_base_url = urlunparse(sanitized_parts)

        if vintage_from_url:
            rebuilt_parts = urlparse(sanitized_base_url)._replace(query=f"year={vintage_from_url}")
            url_for_scraper = urlunparse(rebuilt_parts)
            logger.info(f"Rebuilt clean URL with vintage '{vintage_from_url}' for scraper: '{url_for_scraper}'")
        else:
            url_for_scraper = sanitized_base_url
            logger.warning("App-sourced URL did not contain a 'year' parameter. Scraping as non-vintage.")
    else:
        logger.debug(f"Web-sourced URL detected: '{url_for_scraper}'")

    if not isinstance(quantity, int) or quantity < 1:
        quantity = 1

    wine_data, canonical_url = scraper.scrape_vivino_url(url_for_scraper)
    
    if not wine_data or not canonical_url:
        return jsonify({"status": "error", "message": "Scraping failed: Could not identify valid wine details on the page."}), 500

    if manual_vintage_str:
        try:
            wine_data['vintage'] = int(manual_vintage_str)
            logger.info(f"Overriding vintage with user-provided JSON value: {manual_vintage_str}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid manual vintage value received in JSON: {manual_vintage_str}")

    wine_data['vivino_url'] = canonical_url

    existing_wine_row = db.get_wine_by_url(canonical_url)
    if not existing_wine_row:
        existing_wine_row = db.get_wine_by_name_and_vintage(wine_data['name'], wine_data['vintage'])
    
    if existing_wine_row:
        wine_data['vivino_url'] = existing_wine_row['vivino_url']

    if db.add_or_update_wine(wine_data, quantity, cost_tier):
        updated_wine_row = db.get_wine_by_url(wine_data['vivino_url'])
        if updated_wine_row:
            current_total_quantity = updated_wine_row.get('quantity', 0)
            ha_service.sync_wine_to_todo(updated_wine_row, current_total_quantity)
            ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
            return jsonify({
                "status": "success", "message": "Wine data scraped and stored/updated.",
                "wine_name": updated_wine_row['name'], "vintage": updated_wine_row['vintage'],
                "vivino_url": updated_wine_row['vivino_url'], "quantity_added": quantity,
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
    if not isinstance(quantity, int) or quantity < 1: quantity = 1
    cost_tier = data.get('cost_tier')
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', data['name'].replace(' ', '_')).lower()
    synthetic_url = f"manual:{safe_name}:{data['vintage']}"
    
    existing_wine = db.get_wine_by_url(synthetic_url)
    if not existing_wine:
        existing_wine = db.get_wine_by_name_and_vintage(data['name'], data['vintage'])
    
    if existing_wine: synthetic_url = existing_wine['vivino_url']
    
    wine_data = {
        'vivino_url': synthetic_url, 'name': data['name'], 'vintage': data['vintage'],
        'varietal': data.get('varietal') or "Unknown Varietal",
        'region': data.get('region') or "Unknown Region",
        'country': data.get('country') or "Unknown Country",
        'vivino_rating': None, 'image_url': data.get('image_url'), 'cost_tier': cost_tier,
        'personal_rating': None, 'tasting_notes': data.get('tasting_notes'),
        'alcohol_percent': data.get('alcohol_percent'),
        'wine_type': data.get('wine_type')
    }

    if db.add_or_update_wine(wine_data, quantity, cost_tier):
        updated_wine_row = db.get_wine_by_url(synthetic_url)
        if not updated_wine_row:
             return jsonify({"status": "error", "message": "Failed to retrieve manually added wine."}), 500
        current_total_quantity = updated_wine_row.get('quantity', 0)
        ha_service.sync_wine_to_todo(updated_wine_row, current_total_quantity)
        ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
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
    old_wine_row = db.get_wine_by_url(vivino_url)
    if not old_wine_row:
        return jsonify({"status": "error", "message": "Wine to edit not found."}), 404

    ha_service.sync_wine_to_todo(old_wine_row, 0)
        
    success = db.update_wine_details(
        vivino_url, data['name'], data['vintage'], data['quantity'], data.get('varietal'),
        data.get('region'), data.get('country'), data.get('cost_tier'),
        data.get('personal_rating'), data.get('tasting_notes'),
        data.get('alcohol_percent'), data.get('wine_type')
    )
    
    if not success:
        ha_service.sync_wine_to_todo(old_wine_row, old_wine_row['quantity'])
        return jsonify({"status": "error", "message": "Database error while editing wine."}), 500
    
    updated_wine_row = db.get_wine_by_url(vivino_url)
    if updated_wine_row:
        ha_service.sync_wine_to_todo(updated_wine_row, updated_wine_row['quantity'])
    
    ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
    return jsonify({"status": "success", "message": "Wine updated successfully."}), 200

@app.route('/inventory', methods=['GET'])
def get_inventory():
    status_filter = request.args.get('filter', 'on_hand')
    wines = db.get_all_wines(status_filter)
    for wine in wines:
        wine['b4b_score'] = formatting.calculate_b4b_score(wine)
    return jsonify(wines), 200

@app.route('/inventory/wine/set_quantity', methods=['POST'])
def set_wine_quantity():
    data = request.get_json()
    if not data or 'vivino_url' not in data or 'quantity' not in data:
        return jsonify({"status": "error", "message": "Missing 'vivino_url' or 'quantity'"}), 400
    vivino_url = data['vivino_url']
    new_quantity = data['quantity']
    if not isinstance(new_quantity, int) or new_quantity < 0:
        return jsonify({"status": "error", "message": "Quantity must be a non-negative integer."}), 400
    wine_data = db.get_wine_by_url(vivino_url)
    if not wine_data:
        return jsonify({"status": "error", "message": "Wine not found."}), 404
    if db.update_wine_quantity(vivino_url, new_quantity):
        ha_service.sync_wine_to_todo(wine_data, new_quantity)
        ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
        return jsonify({"status": "success", "message": f"Quantity set to {new_quantity}."}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to update quantity in database."}), 500

@app.route('/api/consume-wine', methods=['POST'])
def consume_wine_from_webhook():
    try:
        data = request.get_json()
        item_text = data.get("item")
        personal_rating = data.get("rating")
        
        if not item_text:
            return jsonify({"status": "error", "message": "Missing 'item' in request body"}), 400

        parsed_name, parsed_vintage = None, None
        if item_text.endswith(')') and item_text[-6:-5] == '(' and item_text[-5:-1].isdigit() and len(item_text) > 6:
            try:
                parsed_vintage = int(item_text[-5:-1])
                parsed_name = item_text[:-6].rstrip()
            except (ValueError, IndexError):
                parsed_name = item_text.strip()
        else:
            parsed_name = item_text.strip()
        
        wine_record = db.get_wine_by_name_and_vintage(parsed_name, parsed_vintage)

        if not wine_record:
            return jsonify({"status": "warning", "message": "No matching wine found."}), 404
        
        vivino_url = wine_record['vivino_url']
        status, message, updated_wine = db.atomically_consume_wine(vivino_url, personal_rating)
        
        if status == "success":
            ha_service.fire_consumption_event(updated_wine)
            ha_service.sync_wine_to_todo(updated_wine, message) # message is new_quantity
            ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
            return jsonify({"status": "success", "message": f"Quantity updated. New quantity: {message}."}), 200
        elif message == "Quantity already zero":
            return jsonify({"status": "warning", "message": "Quantity already zero."}), 404
        else:
            # Covers "Wine not found" and "Database error"
            return jsonify({"status": "error", "message": message}), 500

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
        
    status, message, updated_wine = db.atomically_consume_wine(vivino_url, personal_rating)
    
    if status == "success":
        ha_service.fire_consumption_event(updated_wine)
        ha_service.sync_wine_to_todo(updated_wine, message) # message is new_quantity
        ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
        return jsonify({'status': 'success', 'new_quantity': message})
    elif message == "Wine not found":
        return jsonify({'error': 'Wine not found'}), 404
    elif message == "Quantity already zero":
        return jsonify({'status': 'success', 'new_quantity': 0}) # Still a "success" for the UI
    else:
        return jsonify({'error': message}), 500


@app.route('/inventory/wine', methods=['DELETE'])
def delete_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing 'vivino_url'"}), 400
    wine_to_delete = db.get_wine_by_url(vivino_url)
    if not wine_to_delete:
        return jsonify({"status": "error", "message": "Wine not found."}), 404
    if db.delete_wine_by_url(vivino_url):
        ha_service.sync_wine_to_todo(wine_to_delete, 0)
        ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to delete wine from database."}), 500

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
    if not db.update_personal_rating(vivino_url, rating_val):
        return jsonify({"status": "error", "message": "Wine not found or DB error"}), 404
    updated_wine_row = db.get_wine_by_url(vivino_url)
    if updated_wine_row and updated_wine_row['quantity'] > 0:
        ha_service.sync_wine_to_todo(updated_wine_row, updated_wine_row['quantity'])
    # Note: Rating a wine doesn't change inventory counts,
    # so no sensor update is strictly needed here.
    return jsonify({"status": "success"}), 200

@app.route('/api/wine/notes', methods=['POST'])
def save_tasting_notes_and_image():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing required vivino_url"}), 400
    tasting_notes = data.get('tasting_notes')
    image_url = data.get('image_url')
    image_zoom = data.get('image_zoom')
    image_tilt = data.get('image_tilt')
    
    if tasting_notes is None and image_url is None and image_zoom is None and image_tilt is None:
        return jsonify({"status": "info", "message": "No data provided to update."}), 200
    if db.update_wine_notes_and_image(vivino_url, tasting_notes, image_url, image_zoom, image_tilt):
        return jsonify({"status": "success", "message": "Details saved."}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found or DB error."}), 404

@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha_endpoint():
    try:
        wines = db.get_all_wines(status_filter='all')
        ha_service.force_clear_ha_list()
        ha_service.sync_all_wines_to_ha(wines)
        ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
        return jsonify({"status": "success", "message": "All wines synchronized."}), 200
    except Exception as e:
        logger.error(f"Error during full sync: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal error during sync."}), 500

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    try:
        ha_service.force_clear_ha_list()
        db.reinitialize_database()
        ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
        return jsonify({"status": "success", "message": "Database reinitialized."}), 200
    except Exception as e:
        logger.error(f"Error reinitializing database: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal error during reinitialization."}), 500

@app.route("/backup-database", methods=["POST"])
def backup_db_endpoint():
    try:
        success, message = db.backup_database()
        if success:
            return jsonify({"status": "success", "message": message}), 200
        else:
            return jsonify({"status": "error", "message": message}), 500
    except Exception as e:
        logger.error(f"Error during backup: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Backup failed."}), 500

@app.route("/restore-database", methods=["POST"])
def restore_db_endpoint():
    try:
        success, message = db.restore_database()
        if success:
            wines = db.get_all_wines(status_filter='all')
            ha_service.force_clear_ha_list()
            ha_service.sync_all_wines_to_ha(wines)
            ha_service.trigger_sensor_update() # <--- UPDATE SENSORS
            return jsonify({"status": "success", "message": message}), 200
        else:
            return jsonify({"status": "error", "message": message}), 500
    except Exception as e:
        logger.error(f"Error during restore: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Restore failed."}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """A simple endpoint to verify the server is running."""
    return jsonify({"status": "ok"}), 200

@app.route("/")
def serve_frontend():
    return send_from_directory("../frontend", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("../frontend", path)

# --- MODIFIED STARTUP BLOCK ---
if __name__ == '__main__':
    db.init_db()
    
    # --- NEW: Register MQTT shutdown hook ---
    atexit.register(ha_service.stop_mqtt)

    # --- NEW: Initialize MQTT client if enabled ---
    if config.USE_MQTT_DISCOVERY:
        try:
            logger.info("MQTT Discovery is enabled. Initializing MQTT client...")
            ha_service.initialize_mqtt()
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}", exc_info=True)
    else:
        logger.info("MQTT Discovery is disabled. Using REST API for sensors.")
        # Trigger sensor update on startup for REST-only mode
        try:
            logger.info("Performing initial sync of HA sensors (REST) on startup...")
            ha_service.trigger_sensor_update()
            logger.info("Initial HA sensor (REST) sync complete.")
        except Exception as e:
            logger.error(f"Failed to perform initial HA sensor (REST) sync: {e}", exc_info=True)
    
    # Note: If MQTT is enabled, the initial sensor update will happen
    # automatically inside the `on_connect` callback.
        
    logger.info(f"Starting Wonderful Wino on port 5000 with log level {config.LOG_LEVEL}")
    print("\n---> NOTE: The following 'WARNING' is a standard benign message from the internal web server.\n"
          "---> It is normal and expected for a Home Assistant add-on and can be safely ignored.\n")
    app.run(host='0.0.0.0', port=5000)