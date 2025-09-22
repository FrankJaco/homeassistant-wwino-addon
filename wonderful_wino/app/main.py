import logging
import re
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from . import config, db, scraper, ha_service, formatting

# Get the logger from the config file
logger = logging.getLogger(__name__)

# --- Flask App Setup ---
# The static folder is set to ../../frontend because this file is in app/
app = Flask(__name__, static_folder="../../frontend", static_url_path="")
CORS(app)

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

# --- API Routes ---

@app.route('/api/health')
def health_check():
    """A simple endpoint to confirm the server is running."""
    logger.info("Health check endpoint was called.")
    return jsonify({"status": "ok"})

@app.route('/scan-wine', methods=['POST'])
def scan_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing 'vivino_url'"}), 400

    logger.info(f"Scanning wine from URL: {vivino_url}")
    
    # 1. Scrape data
    wine_data = scraper.scrape_vivino_data(vivino_url)
    if not wine_data:
        logger.error(f"Failed to scrape data from Vivino URL: {vivino_url}")
        return jsonify({"status": "error", "message": "Failed to scrape data from Vivino URL."}), 500
    
    # 2. Add or update in the database
    quantity = data.get('quantity', 1)
    cost_tier = data.get('cost_tier')
    updated_wine = db.add_or_update_wine(wine_data, quantity, cost_tier)
    if not updated_wine:
        logger.error("Failed to store/update wine data in database.")
        return jsonify({"status": "error", "message": "Failed to store/update wine data in database."}), 500

    # 3. Sync to Home Assistant
    ha_service.sync_wine_to_todo(updated_wine, updated_wine['quantity'])

    return jsonify({
        "status": "success",
        "message": "Wine data scraped and stored/updated.",
        "wine_name": updated_wine['name'],
        "vintage": updated_wine['vintage'],
        "current_total_quantity": updated_wine['quantity']
    }), 200

@app.route('/add-manual-wine', methods=['POST'])
def add_manual_wine():
    data = request.get_json()
    required = ['name', 'vintage', 'quantity']
    if not all(field in data for field in required):
        return jsonify({"status": "error", "message": "Missing required fields (name, vintage, quantity)"}), 400

    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', data['name'].replace(' ', '_')).lower()
    synthetic_url = f"manual:{safe_name}:{data['vintage']}"
    
    wine_data = {
        'vivino_url': synthetic_url,
        'name': data['name'],
        'vintage': data['vintage'],
        'varietal': data.get('varietal', "Unknown Varietal"),
        'region': data.get('region', "Unknown Region"),
        'country': data.get('country', "Unknown Country"),
        'vivino_rating': None,
        'image_url': data.get('image_url'),
    }

    quantity = data.get('quantity', 1)
    cost_tier = data.get('cost_tier')
    updated_wine = db.add_or_update_wine(wine_data, quantity, cost_tier)
    
    if updated_wine:
        ha_service.sync_wine_to_todo(updated_wine, updated_wine['quantity'])
        return jsonify({
            "status": "success",
            "message": "Wine manually added/updated successfully.",
            "wine_name": updated_wine['name'],
            "current_total_quantity": updated_wine['quantity']
        }), 200
    else:
        return jsonify({"status": "error", "message": "Failed to store manual wine data."}), 500

@app.route('/edit-wine', methods=['POST'])
def edit_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing vivino_url for editing."}), 400

    old_wine = db.get_wine_by_url(vivino_url)
    if old_wine:
        ha_service.sync_wine_to_todo(old_wine, 0) # Remove old entry from HA
    
    updated_wine = db.update_wine_details(data)
    if updated_wine:
        ha_service.sync_wine_to_todo(updated_wine, updated_wine['quantity'])
        return jsonify({"status": "success", "message": "Wine updated successfully."}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to update wine."}), 500

@app.route('/inventory', methods=['GET'])
def get_inventory():
    status_filter = request.args.get('filter', 'on_hand')
    wines = db.get_all_wines(status_filter)
    
    # Add B4B score to each wine
    for wine in wines:
        wine['b4b_score'] = formatting.calculate_b4b_score(wine)
        
    return jsonify(wines), 200

@app.route('/inventory/wine/set_quantity', methods=['POST'])
def set_wine_quantity():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    quantity = data.get('quantity')
    if not vivino_url or quantity is None:
        return jsonify({"status": "error", "message": "Missing 'vivino_url' or 'quantity'"}), 400

    success = db.set_wine_quantity(vivino_url, quantity)
    if success:
        wine = db.get_wine_by_url(vivino_url)
        ha_service.sync_wine_to_todo(wine, quantity)
        return jsonify({"status": "success", "message": f"Quantity set to {quantity}."}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found."}), 404

@app.route('/api/consume-wine', methods=['POST'])
def consume_wine_from_webhook():
    data = request.get_json()
    item_text = data.get("item")
    personal_rating = data.get("rating")
    
    if not item_text:
        return jsonify({"status": "error", "message": "Missing 'item' in request body"}), 400

    wine = db.consume_wine_by_name_vintage(item_text, personal_rating)
    if wine:
        ha_service.sync_wine_to_todo(wine, wine['quantity'])
        return jsonify({"status": "success", "message": f"Quantity updated. New quantity: {wine['quantity']}."}), 200
    else:
        return jsonify({"status": "warning", "message": "No matching wine found to consume."}), 404

@app.route('/inventory/wine/consume', methods=['POST'])
def consume_wine_from_ui():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    personal_rating = data.get('personal_rating')

    if not vivino_url:
        return jsonify({'error': 'vivino_url is required'}), 400
    
    wine = db.consume_wine_by_url(vivino_url, personal_rating)
    if wine:
        ha_service.sync_wine_to_todo(wine, wine['new_quantity'])
        return jsonify({'status': 'success', 'new_quantity': wine['new_quantity']})
    else:
        return jsonify({'error': 'Wine not found or already at 0 quantity'}), 404

@app.route('/inventory/wine', methods=['DELETE'])
def delete_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing 'vivino_url'"}), 400

    wine_to_delete = db.get_wine_by_url(vivino_url)
    success = db.delete_wine_by_url(vivino_url)

    if success:
        if wine_to_delete:
            ha_service.sync_wine_to_todo(wine_to_delete, 0) # Remove from HA
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found."}), 404

@app.route('/api/rate-wine', methods=['POST'])
def rate_wine():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    personal_rating = data.get('personal_rating')

    if not vivino_url or personal_rating is None:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    updated_wine = db.rate_wine_by_url(vivino_url, personal_rating)
    if updated_wine:
        if updated_wine['quantity'] > 0:
            ha_service.sync_wine_to_todo(updated_wine, updated_wine['quantity'])
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found"}), 404

@app.route('/api/wine/notes', methods=['POST'])
def save_wine_notes():
    data = request.get_json()
    vivino_url = data.get('vivino_url')
    if not vivino_url:
        return jsonify({"status": "error", "message": "Missing vivino_url"}), 400
    
    success = db.update_wine_notes(data)
    if success:
        return jsonify({"status": "success", "message": "Details saved."}), 200
    else:
        return jsonify({"status": "error", "message": "Wine not found"}), 404

@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines():
    wines = db.get_all_wines(status_filter='all')
    ha_service.sync_all_wines_to_ha(wines)
    return jsonify({"status": "success", "message": "All wines synchronized."}), 200

@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_route():
    db.reinitialize_database()
    return jsonify({"status": "success", "message": "Database reinitialized."}), 200

@app.route("/backup-database", methods=["POST"])
def backup_db_route():
    success, message = db.backup_database()
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500

@app.route("/restore-database", methods=["POST"])
def restore_db_route():
    success, message = db.restore_database()
    if success:
        # After a restore, it's a good idea to re-sync everything to HA
        wines = db.get_all_wines(status_filter='on_hand')
        ha_service.sync_all_wines_to_ha(wines)
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500

# --- Settings Routes ---
@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = db.get_all_settings()
    return jsonify(settings), 200

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    success = db.save_settings(data)
    if success:
        return jsonify({"status": "success", "message": "Settings updated."}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to update settings."}), 500

# --- Frontend Serving ---
@app.route("/")
def serve_frontend_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_frontend_static(path):
    return send_from_directory(app.static_folder, path)


# --- Main Execution ---
if __name__ == '__main__':
    db.init_db() # Initialize the database on startup
    logger.info(f"Starting Wonderful Wino on port 5000 with log level {config.LOG_LEVEL}")
    app.run(host='0.0.0.0', port=5000)

