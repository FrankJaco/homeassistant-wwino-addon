import requests
import logging
from . import config
from . import formatting

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

def _get_ha_todo_items(headers):
    """Fetches all items from the HA To-Do list entity."""
    if not config.HOME_ASSISTANT_URL or not config.TODO_LIST_ENTITY_ID:
        logger.error("Cannot get HA items: Missing URL or Entity ID.")
        return []
    
    # The get_items service call is a bit different, it returns state data
    url = f"{config.HOME_ASSISTANT_URL}/api/states/{config.TODO_LIST_ENTITY_ID}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        # The items are stored in an attribute called 'todo' with 'summary' as the key for the item name
        # This structure can vary, but this is common for local todo lists
        if 'attributes' in data and 'todo' in data['attributes']:
            return [item['summary'] for item in data['attributes']['todo']]
        else:
            # Fallback for other possible structures
            logger.warning("Could not find 'todo' attribute in HA entity. Trying to call 'get_items' service.")
            service_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/get_items"
            payload = {"entity_id": config.TODO_LIST_ENTITY_ID}
            service_response = requests.post(service_url, json=payload, headers=headers, timeout=10)
            service_response.raise_for_status()
            service_data = service_response.json()
            if service_data and 'items' in service_data.get(config.TODO_LIST_ENTITY_ID, {}):
                return [item['summary'] for item in service_data[config.TODO_LIST_ENTITY_ID]['items']]

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get items from HA To-Do list: {e}")
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error parsing items from HA To-Do list response: {e}")
    
    return []


def _remove_ha_todo_item(item_text, headers):
    """Removes a single item from the HA To-Do list."""
    remove_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    payload = {
        "entity_id": config.TODO_LIST_ENTITY_ID,
        "item": item_text
    }
    try:
        resp = requests.post(remove_url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 400 and "Unable to find" in resp.text:
            logger.debug(f"Item '{item_text}' not found in HA to remove (this is OK).")
        else:
            resp.raise_for_status()
            logger.info(f"Successfully removed '{item_text}' from HA To-Do list.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to remove '{item_text}' from HA To-Do list: {e}")


def sync_wine_to_todo(wine: dict, current_quantity: int):
    """
    Adds, updates, or removes a single wine item from the HA To-Do list.
    This is an idempotent operation: it first removes, then re-adds if quantity > 0.
    """
    headers = _get_ha_headers()
    if not headers or not config.HOME_ASSISTANT_URL or not config.TODO_LIST_ENTITY_ID:
        logger.error("Cannot sync to HA: Missing URL, Token, or Entity ID configuration.")
        return

    item_text = formatting.format_wine_for_todo(wine)
    
    # 1. Always remove the old item first to ensure updates are reflected.
    _remove_ha_todo_item(item_text, headers)

    # 2. If quantity is positive, re-add the item with the updated description.
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
            logger.info(f"Successfully added/updated '{item_text}' in HA To-Do list.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to add/update '{item_text}' in HA To-Do list: {e}")

def sync_all_wines_to_ha(all_wines: list):
    """
    Performs a full synchronization of wines to the HA To-Do list, making it a mirror of the local DB.
    """
    logger.info(f"Starting full synchronization of {len(all_wines)} wines to HA To-Do list.")
    headers = _get_ha_headers()
    if not headers:
        return

    # 1. Get the desired state from our local database.
    db_wine_names = {formatting.format_wine_for_todo(wine) for wine in all_wines}

    # 2. Get the current state from Home Assistant.
    ha_item_names = set(_get_ha_todo_items(headers))
    logger.debug(f"Found {len(ha_item_names)} items in HA: {ha_item_names}")
    logger.debug(f"Found {len(db_wine_names)} wines in DB: {db_wine_names}")

    # 3. Determine which items to remove from HA.
    items_to_remove = ha_item_names - db_wine_names
    if items_to_remove:
        logger.info(f"Removing {len(items_to_remove)} items from HA that are not in the local DB.")
        for item_text in items_to_remove:
            _remove_ha_todo_item(item_text, headers)

    # 4. Add or update all wines from our database.
    # The sync_wine_to_todo function is idempotent (remove then add), so it's safe to run for all.
    if all_wines:
        logger.info(f"Adding/updating {len(all_wines)} wines in HA.")
    for wine in all_wines:
        # We only need to sync items with quantity > 0
        if wine.get('quantity', 0) > 0:
            sync_wine_to_todo(wine, wine.get('quantity'))

    logger.info("Completed full synchronization.")