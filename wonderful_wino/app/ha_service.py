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
    """Removes a single item from the HA To-Do list."""
    remove_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    payload = { "entity_id": config.TODO_LIST_ENTITY_ID, "item": item_text }
    try:
        resp = requests.post(remove_url, json=payload, headers=headers, timeout=5)
        # Check for specific "not found" text within common error codes
        if resp.status_code >= 400 and "Unable to find item" in resp.text:
             logger.info(f"Item '{item_text}' not found on To-Do list (expected for new wines).")
        else:
            # Raise an exception for other errors (like 500, 401, 403 etc.)
            resp.raise_for_status()
            logger.info(f"Successfully removed '{item_text}' from HA To-Do list.")
    except requests.exceptions.HTTPError as e:
        # This block now specifically catches the HTTP errors raised by raise_for_status()
        # This is where the 500 Internal Server Error will land.
        if e.response.status_code == 500 and "Unable to find item" in e.response.text:
            logger.info(f"Item '{item_text}' not found on To-Do list (expected for new wines).")
        else:
            # Log all other unexpected HTTP errors as warnings
            logger.warning(f"Could not remove '{item_text}' from HA To-Do. Error: {e}")
    except requests.exceptions.RequestException as e:
        # Catch other network-related issues (timeout, connection error)
        logger.warning(f"Could not remove '{item_text}' from HA To-Do. Network Error: {e}")


def sync_wine_to_todo(wine: dict, current_quantity: int):
    """Adds, updates, or removes a single wine item from the HA To-Do list."""
    headers = _get_ha_headers()
    if not headers or not config.HOME_ASSISTANT_URL or not config.TODO_LIST_ENTITY_ID:
        logger.error("Cannot sync to HA: Missing URL, Token, or Entity ID configuration.")
        return
    
    item_text = formatting.format_wine_for_todo(wine)
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
            logger.info(f"Successfully synced '{item_text}' to HA To-Do list.")
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

