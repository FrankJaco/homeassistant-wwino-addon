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
    
    # 1. Always attempt to remove the old item first to ensure updates are reflected.
    remove_url = f"{config.HOME_ASSISTANT_URL}/api/services/todo/remove_item"
    remove_payload = {
        "entity_id": config.TODO_LIST_ENTITY_ID,
        "item": item_text
    }
    
    try:
        resp = requests.post(remove_url, json=remove_payload, headers=headers, timeout=5)
        # We expect this might fail if the item isn't there, which is fine.
        if resp.status_code == 400 and "Unable to find" in resp.text:
             logger.debug(f"Item '{item_text}' not found in HA To-Do list (normal for new items).")
        else:
            resp.raise_for_status() # Raise for other errors (e.g., 401 Unauthorized)
            logger.info(f"Successfully removed '{item_text}' from HA To-Do list for update.")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not remove '{item_text}' from HA To-Do. This is safe to ignore if adding for the first time. Error: {e}")

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
            logger.info(f"Successfully synced '{item_text}' to HA To-Do list with quantity {current_quantity}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to add/update '{item_text}' in HA To-Do list: {e}")
    else:
        logger.info(f"Quantity for '{item_text}' is 0. Item was removed and not re-added from HA To-Do list.")

def sync_all_wines_to_ha(all_wines: list):
    """
    Performs a full synchronization of a list of wines to the HA To-Do list.
    """
    logger.info(f"Starting full synchronization of {len(all_wines)} wines to HA To-Do list.")
    for wine in all_wines:
        sync_wine_to_todo(wine, wine.get('quantity', 0))
    logger.info("Completed full synchronization.")
