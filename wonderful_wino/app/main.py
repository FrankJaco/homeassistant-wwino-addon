import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from . import config, db, ha_service, scraper, formatting
import re
from urllib.parse import urlparse, urlunparse, parse_qs

# --- MODIFIED: Logging Configuration ---
# Quieten down the very verbose output from underlying libraries
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Configure the root logger for the application
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# --- END MODIFIED SECTION ---

logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

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

# --- Flask Routes ---
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

    wine_data, canonical_url = scraper.scrape_vivino_data(url_for_scraper)
    
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
        'personal_rating': None, 'tasting_notes': data.get('tasting_notes')
    }

    if db.add_or_update_wine(wine_data, quantity, cost_tier):
        updated_wine_row = db.get_wine_by_url(synthetic_url)
        if not updated_wine_row:
             return jsonify({"status": "error", "message": "Failed to retrieve manually added wine."}), 500
        current_total_quantity = updated_wine_row.get('quantity', 0)
        ha_service.sync_wine_to_todo(updated_wine_row, current_total_quantity)
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
        data.get('personal_rating'), data.get('tasting_notes')
    )
    
    if not success:
        ha_service.sync_wine_to_todo(old_wine_row, old_wine_row['quantity'])
        return jsonify({"status": "error", "message": "Database error while editing wine."}), 500
    
    updated_wine_row = db.get_wine_by_url(vivino_url)
    if updated_wine_row:
        ha_service.sync_wine_to_todo(updated_wine_row, updated_wine_row['quantity'])
    
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
        
        if wine_record.get('quantity', 0) > 0:
            new_quantity = wine_record['quantity'] - 1
            updated_wine = db.update_wine_quantity_and_rating(wine_record['vivino_url'], new_quantity, personal_rating)
            
            if updated_wine:
                db.add_consumption_record(updated_wine['id'], personal_rating)
                ha_service.fire_consumption_event(updated_wine)
                ha_service.sync_wine_to_todo(updated_wine, new_quantity) 
                return jsonify({"status": "success", "message": f"Quantity updated. New quantity: {new_quantity}."}), 200
            else:
                return jsonify({"status": "error", "message": "Failed to update wine in database."}), 500
        else:
            return jsonify({"status": "warning", "message": "Quantity already zero."}), 404

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
        
    wine_data = db.get_wine_by_url(vivino_url)
    if not wine_data:
        return jsonify({'error': 'Wine not found'}), 404
        
    if wine_data['quantity'] > 0:
        new_quantity = wine_data['quantity'] - 1
        updated_wine = db.update_wine_quantity_and_rating(vivino_url, new_quantity, personal_rating)

        if updated_wine:
            db.add_consumption_record(updated_wine['id'], personal_rating)
            ha_service.fire_consumption_event(updated_wine)
            ha_service.sync_wine_to_todo(updated_wine, new_quantity)
            return jsonify({'status': 'success', 'new_quantity': new_quantity})
        else:
            return jsonify({'error': 'Failed to update wine in database'}), 500
    
    return jsonify({'status': 'success', 'new_quantity': wine_data['quantity']})

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
    return jsonify({"status": "success"}), 200

@app.route('/api/wine/notes', methods=['POST'])
def save_tasting_notes_and_image():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing required vivino_url"}), 400
    tasting_notes = data.get('tasting_notes')
    image_url = data.get('image_url')
    if tasting_notes is None and image_url is None:
        return jsonify({"status": "info", "message": "No data provided to update."}), 200
    if db.update_wine_notes_and_image(vivino_url, tasting_notes, image_url):
        return jsonify({"status": "success", "message": "Details saved."}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found or DB error."}), 404

@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha_endpoint():
    try:
        wines = db.get_all_wines(status_filter='all')
        ha_service.force_clear_ha_list()
        ha_service.sync_all_wines_to_ha(wines)
        return jsonify({"status": "success", "message": "All wines synchronized."}), 200
    except Exception as e:
        logger.error(f"Error during full sync: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal error during sync."}), 500

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    try:
        ha_service.force_clear_ha_list()
        db.reinitialize_database()
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

if __name__ == '__main__':
    db.init_db()
    logger.info(f"Starting Wonderful Wino on port 5000 with log level {config.LOG_LEVEL}")
    app.run(host='0.0.0.0', port=5000)
