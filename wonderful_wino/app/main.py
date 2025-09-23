# main.py

import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from . import config, db, ha_service, scraper, formatting
import re

# Get the logger from the config file
logger = logging.getLogger(__name__)

# --- Flask App Setup ---
app = Flask(__name__, static_folder="../frontend", static_url_path="")
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

    wine_data = scraper.scrape_vivino_data(vivino_url)
    if not wine_data:
        return jsonify({"status": "error", "message": "Failed to scrape data from Vivino URL."}), 500

    # **FIX:** Restore original logic to prevent duplicates.
    # First, try to find a wine by the exact URL.
    # If not found, fall back to checking by name and vintage.
    existing_wine_row = db.get_wine_by_url(vivino_url)
    if not existing_wine_row:
        existing_wine_row = db.get_wine_by_name_and_vintage(wine_data['name'], wine_data['vintage'])
    
    # If an existing wine was found by either method, use its URL as the canonical one.
    if existing_wine_row:
        wine_data['vivino_url'] = existing_wine_row['vivino_url']

    if db.add_or_update_wine(wine_data, quantity, cost_tier):
        # Use the canonical URL to fetch the final, updated record.
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
    if not isinstance(quantity, int) or quantity < 1:
        quantity = 1
    cost_tier = data.get('cost_tier')
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', data['name'].replace(' ', '_')).lower()
    synthetic_url = f"manual:{safe_name}:{data['vintage']}"
    
    # **FIX:** When manually adding, check if it already exists to avoid overwriting.
    existing_wine = db.get_wine_by_url(synthetic_url)
    if not existing_wine:
        existing_wine = db.get_wine_by_name_and_vintage(data['name'], data['vintage'])
    
    if existing_wine:
        synthetic_url = existing_wine['vivino_url']
    
    wine_data = {
        'vivino_url': synthetic_url, 'name': data['name'], 'vintage': data['vintage'],
        'varietal': data.get('varietal') or "Unknown Varietal",
        'region': data.get('region') or "Unknown Region",
        'country': data.get('country') or "Unknown Country",
        'vivino_rating': None,
        'image_url': data.get('image_url'),
        'cost_tier': cost_tier,
        'personal_rating': None,
        'tasting_notes': data.get('tasting_notes')
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
        # **FIX:** Added error handling for when the wine to edit doesn't exist.
        return jsonify({"status": "error", "message": "Wine to edit not found."}), 404

    # First, remove the old item from the To-Do list to prevent duplicates
    ha_service.sync_wine_to_todo(old_wine_row, 0)
        
    # Update the wine in the database
    success = db.update_wine_details(
        vivino_url,
        data['name'],
        data['vintage'],
        data['quantity'],
        data.get('varietal'),
        data.get('region'),
        data.get('country'),
        data.get('cost_tier'),
        data.get('personal_rating'),
        data.get('tasting_notes')
    )
    
    if not success:
        # **FIX:** Added error handling in case the database update fails.
        # Re-sync the old data to avoid leaving the to-do list in a bad state.
        ha_service.sync_wine_to_todo(old_wine_row, old_wine_row['quantity'])
        return jsonify({"status": "error", "message": "Database error while editing wine."}), 500
    
    # Re-sync the updated wine to the To-Do list
    updated_wine_row = db.get_wine_by_url(vivino_url)
    if updated_wine_row:
        ha_service.sync_wine_to_todo(updated_wine_row, updated_wine_row['quantity'])
    
    return jsonify({"status": "success", "message": "Wine updated successfully."}), 200


@app.route('/inventory', methods=['GET'])
def get_inventory():
    status_filter = request.args.get('filter', 'on_hand')
    wines = db.get_all_wines(status_filter)
    
    # Calculate B4B score for each wine on the fly
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
            logger.error("Webhook received without 'item' text.")
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
        
        current_db_quantity = wine_record.get('quantity', 0)
        
        if current_db_quantity > 0:
            new_quantity = current_db_quantity - 1
            updated_wine = db.update_wine_quantity_and_rating(wine_record['vivino_url'], new_quantity, personal_rating)
            if updated_wine:
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
        
    current_quantity = wine_data['quantity']
    new_quantity = current_quantity
    
    if current_quantity > 0:
        new_quantity = current_quantity - 1
        updated_wine = db.update_wine_quantity_and_rating(vivino_url, new_quantity, personal_rating)
        if updated_wine:
            ha_service.sync_wine_to_todo(updated_wine, new_quantity)
            return jsonify({'status': 'success', 'new_quantity': new_quantity})
        else:
            return jsonify({'error': 'Failed to update wine in database'}), 500
    
    # If quantity was already 0, just return the current state
    return jsonify({'status': 'success', 'new_quantity': new_quantity})


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
        # The function returns False if the wine wasn't found or an error occurred.
        return jsonify({"status": "error", "message": "Wine not found or DB error."}), 404


@app.route("/sync-all-wines", methods=["POST"])
def sync_all_wines_to_ha_endpoint(): # Renamed to avoid conflict
    try:
        wines = db.get_all_wines()
        ha_service.sync_all_wines(wines)
        return jsonify({"status": "success", "message": "All wines synchronized."}), 200
    except Exception as e:
        logger.error(f"Error during full sync: {e}")
        return jsonify({"status": "error", "message": "Internal error during sync."}), 500


@app.route("/reinitialize-database-action", methods=["POST"])
def reinitialize_db_endpoint():
    try:
        db.reinitialize_database()
        ha_service.sync_all_wines([]) # Clear HA to-do list
        return jsonify({"status": "success", "message": "Database reinitialized."}), 200
    except Exception as e:
        logger.error(f"Error reinitializing database: {e}")
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
        logger.error(f"Error during backup: {e}")
        return jsonify({"status": "error", "message": "Backup failed."}), 500


@app.route("/restore-database", methods=["POST"])
def restore_db_endpoint():
    try:
        success, message = db.restore_database()
        if success:
            wines = db.get_all_wines()
            ha_service.sync_all_wines(wines)
            return jsonify({"status": "success", "message": message}), 200
        else:
            return jsonify({"status": "error", "message": message}), 500
    except Exception as e:
        logger.error(f"Error during restore: {e}")
        return jsonify({"status": "error", "message": "Restore failed."}), 500


@app.route("/")
def serve_frontend():
    return send_from_directory("../frontend", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("../frontend", path)

# --- Main Execution ---
if __name__ == '__main__':
    db.init_db()
    logger.info(f"Starting Wonderful Wino on port 5000 with log level {config.LOG_LEVEL}")
    app.run(host='0.0.0.0', port=5000)