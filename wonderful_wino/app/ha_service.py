import requests
import logging
import json
from . import config
from . import formatting
from . import db

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

# --- Private Helpers for HA Communication ---

def _get_ha_headers():
    """Returns the authorization headers for HA API calls."""
    if not config.HOME_ASSISTANT_URL or not config.HA_LONG_LIVED_TOKEN:
        # This is not strictly an error if HA integration is optional, but we log it
        logger.debug("HA integration disabled: URL or Token not configured.")
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
            # We use debug here because trying to remove an item that was already consumed/deleted is expected
            logger.debug(f"Pre-sync cleanup for '{item_text}' failed with status {resp.status_code}. This is normal if the item is new.")
        else:
            logger.info(f"Successfully cleared old item '{item_text}' from HA To-Do list.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to remove item '{item_text}' from HA To-Do list: {e}")

def _add_ha_todo_item(item_text, headers):
    """Fires an 'add_item' call to HA and logs the outcome."""
    add_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/add_item"
    payload = { "entity_id": config.TODO_LIST_ENTITY_ID, "item": item_text }
    try:
        resp = requests.post(add_url, json=payload, headers=headers, timeout=5)
        resp.raise_for_status()
        logger.info(f"Successfully added/updated item '{item_text}' on HA To-Do list.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to add item '{item_text}' to HA To-Do list: {e}")

def _update_ha_state(entity_id: str, state: str, attributes: dict, headers: dict):
    """Updates the state of a single Home Assistant entity."""
    url = f"{config.HOME_ASSISTANT_URL}/api/states/{entity_id}"
    payload = {
        "state": str(state),
        "attributes": attributes
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        resp.raise_for_status()
        logger.debug(f"Successfully updated HA entity: {entity_id} to state: {state}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update HA entity {entity_id}: {e}")

# --- Public Functions for HA Integration ---

def sync_wine_to_todo(wine_data: dict, new_quantity: int):
    """
    Updates the item on the HA To-Do list. 
    It removes the item with the *old* quantity and adds it with the *new* quantity.
    """
    headers = _get_ha_headers()
    if not headers or not config.TODO_LIST_ENTITY_ID:
        return

    # 1. Generate the text format for the item with the new quantity
    # NOTE: This uses the minimal format for reliable removal/addition
    new_item_text = formatting.format_wine_for_ha_todo(wine_data, new_quantity)
    
    # 2. If the quantity is 0, we only remove it and are done.
    if new_quantity <= 0:
        _remove_ha_todo_item(new_item_text, headers)
        return

    # 3. For quantity > 0, we must ensure we update the item correctly in the list.
    # The To-Do list does not have an "update" function, only add/remove.
    # To reliably update, we remove the item with any potential old quantity, and then add the new one.
    
    # We use the new_item_text for removal because only the minimal name/vintage are used to identify the item.
    _remove_ha_todo_item(new_item_text, headers) # Clean up existing item if it's there
    _add_ha_todo_item(new_item_text, headers) # Add the new, correct item

def fire_wine_consumed_event(wine_data: dict, consumed_quantity: int):
    """Fires a Home Assistant event when a wine is consumed."""
    headers = _get_ha_headers()
    if not headers:
        return

    event_url = f"{config.HOME_ASSISTANT_URL}/api/events/wonderful_wino_wine_consumed"
    
    # Create the payload for the event
    payload = {
        "name": wine_data.get('name'),
        "vintage": wine_data.get('vintage'),
        "quantity_consumed": consumed_quantity,
        "vivino_url": wine_data.get('vivino_url'),
        "wine_type": wine_data.get('wine_type', 'Unknown'),
        "country": wine_data.get('country', 'Unknown'),
        "region_full": wine_data.get('region_full', 'Unknown'),
        "vivino_rating": wine_data.get('vivino_rating', None),
        "alcohol_percent": wine_data.get('alcohol_percent', None),
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

    # Use all wines ever added to ensure total cleanup
    historical_wines = db.get_all_historical_wines()
    if not historical_wines:
        logger.info("No historical wines found in DB to clear from HA.")
        return

    for wine in historical_wines:
        # Use a quantity of 0 for the item text to ensure we match and remove the item
        minimal_item_text = formatting.format_wine_for_ha_todo(wine, 0) 
        _remove_ha_todo_item(minimal_item_text, headers)
        
    logger.warning("Force-clear process completed.")

def update_ha_inventory_sensors():
    """
    Updates a set of sensors in Home Assistant based on the current inventory summary.
    This is the function called by the periodic background thread.
    """
    headers = _get_ha_headers()
    if not headers:
        return
        
    try:
        counts = db.get_inventory_counts()
        wines_to_review_count = db.get_wines_needing_review_count()
        
        # Define the sensors to update
        SENSOR_DEFINITIONS = {
            "sensor.wwino_total_bottles": {
                "state": counts.get('total_quantity', 0),
                "attributes": {"unit_of_measurement": "bottles", "friendly_name": "Wino Total Inventory"}
            },
            "sensor.wwino_unique_wines": {
                "state": counts.get('unique_wines', 0),
                "attributes": {"unit_of_measurement": "wines", "friendly_name": "Wino Unique Wines"}
            },
            "sensor.wwino_red_bottles": {
                "state": counts.get('Red', 0),
                "attributes": {"unit_of_measurement": "bottles", "friendly_name": "Wino Red Bottles"}
            },
            "sensor.wwino_white_bottles": {
                "state": counts.get('White', 0),
                "attributes": {"unit_of_measurement": "bottles", "friendly_name": "Wino White Bottles"}
            },
            "sensor.wwino_sparkling_bottles": {
                "state": counts.get('Sparkling', 0) + counts.get('Rosé', 0), # Include Rosé in sparkling for a common grouping
                "attributes": {"unit_of_measurement": "bottles", "friendly_name": "Wino Sparkling/Rosé Bottles"}
            },
            "sensor.wwino_needs_review": {
                "state": wines_to_review_count,
                "attributes": {"unit_of_measurement": "wines", "friendly_name": "Wino Wines Needing Review"}
            },
        }

        # Update all defined sensors
        for entity_id, data in SENSOR_DEFINITIONS.items():
            _update_ha_state(entity_id, data["state"], data["attributes"], headers)

        logger.info("Successfully updated HA inventory sensors.")
        
    except Exception as e:
        logger.error(f"Failed to fetch data or update HA sensors: {e}", exc_info=True)