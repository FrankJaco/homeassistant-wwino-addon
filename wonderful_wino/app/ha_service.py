import requests
import logging
from . import config
from . import formatting
from . import db

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

def _get_ha_headers():
    """Returns the authorization headers for HA API calls."""
    if not config.HA_LONG_LIVED_TOKEN:
        logger.error("Home Assistant Long-Lived Token is not configured.")
        return None
    return {
        "Authorization": f"Bearer {config.HA_LONG_LIVED_TOKEN}",
        "Content-Type": "application/json",
    }

def _remove_ha_todo_item(item_text, headers):
    """Fires a 'remove_item' call to HA and logs the outcome without halting."""
    remove_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    payload = { "entity_id": config.TODO_LIST_ENTITY_ID, "item": item_text }
    try:
        resp = requests.post(remove_url, json=payload, headers=headers, timeout=5)
        # Check for any non-successful status code.
        if resp.status_code >= 400:
            logger.debug(f"Pre-sync cleanup for '{item_text}' failed with status {resp.status_code}. This is normal if the item is new.")
        else:
            logger.info(f"Successfully cleared old item '{item_text}' from HA To-Do list.")
    except requests.exceptions.RequestException:
        # If the request fails entirely, log it quietly and move on.
        logger.debug(f"Pre-sync cleanup for '{item_text}' failed with a network error. Proceeding.")

def sync_wine_to_todo(wine: dict, current_quantity: int):
    """Adds, updates, or removes a single wine item from the HA To-Do list."""
    headers = _get_ha_headers()
    if not headers or not config.HOME_ASSISTANT_URL or not config.TODO_LIST_ENTITY_ID:
        logger.error("Cannot sync to HA: Missing URL, Token, or Entity ID configuration.")
        return
    
    item_text = formatting.format_wine_for_todo(wine)
    
    logger.info(f"Starting sync for '{item_text}'.")
    
    # Perform the "fire and forget" removal of any existing item.
    _remove_ha_todo_item(item_text, headers)

    if current_quantity > 0:
        description = formatting.build_markdown_description(wine, current_quantity)
        add_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/add_item"
        add_payload = {
            "entity_id": config.TODO_LIST_ENTITY_ID,
            "item": item_text,
            "description": description
        }
        try:
            resp = requests.post(add_url, json=add_payload, headers=headers, timeout=5)
            resp.raise_for_status()
            # Use a clear, general-purpose success message.
            logger.info(f"Successfully synced '{item_text}' to the HA To-Do list.")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to add/update '{item_text}' in HA To-Do list: {e}")

def fire_consumption_event(wine_data: dict):
    """Fires a 'wonderful_wino_wine_consumed' event to the HA event bus."""
    headers = _get_ha_headers()
    if not headers or not config.HOME_ASSISTANT_URL:
        logger.error("Cannot fire HA event: Missing URL or Token configuration.")
        return

    event_url = f"{config.HOME_ASSISTANT_URL}/api/events/wonderful_wino_wine_consumed"
    payload = {
        "name": wine_data.get('name'),
        "vintage": wine_data.get('vintage'),
        "varietal": wine_data.get('varietal'),
        "region": wine_data.get('region'),
        "country": wine_data.get('country'),
        "personal_rating": wine_data.get('personal_rating'),
        "vivino_url": wine_data.get('vivino_url')
    }
    try:
        resp = requests.post(event_url, json=payload, headers=headers, timeout=5)
        resp.raise_for_status()
        logger.info(f"Successfully fired 'wonderful_wino_wine_consumed' event for '{wine_data.get('name')}'")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fire HA event: {e}")


def sync_all_wines_to_ha(all_wines: list):
    """Performs a simple sync of all provided wines to the HA To-Do list."""
    logger.info(f"Starting sync of {len(all_wines)} wines to HA To-Do list.")
    on_hand_wines = [wine for wine in all_wines if wine.get('quantity', 0) > 0]
    for wine in on_hand_wines:
        sync_wine_to_todo(wine, wine.get('quantity', 0))
    logger.info("Completed sync.")

def force_clear_ha_list():
    """Gets all wines ever in the DB and attempts to remove them from HA."""
    logger.warning("Performing a force-clear of Home Assistant To-Do list.")
    headers = _get_ha_headers()
    if not headers:
        return

    historical_wines = db.get_all_historical_wines()
    if not historical_wines:
        logger.info("No historical wines found in DB to clear from HA.")
        return

    logger.info(f"Attempting to remove {len(historical_wines)} historical wine entries from HA.")
    for wine in historical_wines:
        item_text = formatting.format_wine_for_todo(wine)
        _remove_ha_todo_item(item_text, headers)
    
    logger.info("Force-clear operation completed.")


# --- NEW FUNCTIONS FOR HA SENSORS ---

SENSOR_DEFINITIONS = {
    'total_bottles': {
        'name': 'wwino_total_bottles',
        'friendly_name': 'Wino Total Inventory',
        'unit': 'bottles',
        'icon': 'mdi:bottle-wine'
    },
    'red_bottles': {
        'name': 'wwino_red_bottles',
        'friendly_name': 'Wino Red Bottles',
        'unit': 'bottles',
        'icon': 'mdi:bottle-wine-outline'
    },
    'white_bottles': {
        'name': 'wwino_white_bottles',
        'friendly_name': 'Wino White Bottles',
        'unit': 'bottles',
        'icon': 'mdi:bottle-wine-outline'
    },
    'sparkling_bottles': {
        'name': 'wwino_sparkling_bottles',
        'friendly_name': 'Wino Sparkling Bottles',
        'unit': 'bottles',
        'icon': 'mdi:bottle-wine-outline'
    },
    'rose_bottles': {
        'name': 'wwino_rose_bottles',
        'friendly_name': 'Wino Rosé Bottles',
        'unit': 'bottles',
        'icon': 'mdi:bottle-wine-outline'
    },
    'dessert_bottles': {
        'name': 'wwino_dessert_bottles',
        'friendly_name': 'Wino Dessert Bottles',
        'unit': 'bottles',
        'icon': 'mdi:bottle-wine-outline'
    },
    'unique_wines': {
        'name': 'wwino_unique_wines',
        'friendly_name': 'Wino Unique Wines',
        'unit': 'wines',
        'icon': 'mdi:glass-wine'
    },
    'needs_review': {
        'name': 'wwino_needs_review',
        'friendly_name': 'Wino Wines Needing Review',
        'unit': 'wines',
        'icon': 'mdi:alert-circle-outline'
    }
}

def update_ha_sensors(stats: dict):
    """
    Pushes all inventory statistics to Home Assistant as sensor states.
    """
    headers = _get_ha_headers()
    if not headers or not config.HOME_ASSISTANT_URL:
        logger.error("Cannot update HA sensors: Missing URL or Token configuration.")
        return

    for key, sensor_info in SENSOR_DEFINITIONS.items():
        state_value = stats.get(key, 0)
        entity_id = f"sensor.{sensor_info['name']}"
        sensor_url = f"{config.HOME_ASSISTANT_URL}/api/states/{entity_id}"
        
        payload = {
            "state": str(state_value),
            "attributes": {
                "unit_of_measurement": sensor_info['unit'],
                "friendly_name": sensor_info['friendly_name'],
                "icon": sensor_info['icon']
            }
        }
        
        try:
            resp = requests.post(sensor_url, json=payload, headers=headers, timeout=3)
            resp.raise_for_status()
            logger.debug(f"Successfully updated HA sensor: {entity_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update HA sensor {entity_id}: {e}")

def trigger_sensor_update():
    """
    A single function to fetch statistics and update HA sensors.
    This is called by main.py whenever the inventory changes.
    """
    try:
        stats = db.get_inventory_statistics()
        if stats:
            update_ha_sensors(stats)
        else:
            logger.warning("Could not retrieve stats to update HA sensors.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during trigger_sensor_update: {e}", exc_info=True)