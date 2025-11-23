import requests
import logging
import json
import os 
import paho.mqtt.client as mqtt
import time # <--- NEW IMPORT
from . import config
from . import formatting
from . import db

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

# --- NEW MQTT Globals ---
mqtt_client = None
is_mqtt_connected = False
MQTT_AVAILABILITY_TOPIC = "wonderful_wino/status"
MQTT_DEVICE_CONFIG = {
    "identifiers": ["wonderful_wino_addon"],
    "name": "Wonderful Wino",
    "manufacturer": "Wonderful Wino Add-on",
    "model": f"v{os.environ.get('VERSION', '1.0.0')}" # Assumes VERSION is in env
}

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc, properties=None):
    """Callback for when the client connects to the MQTT broker."""
    global is_mqtt_connected
    if rc == 0:
        logger.info(f"Successfully connected to MQTT broker at {config.MQTT_HOST}")
        is_mqtt_connected = True
        # Publish device availability
        client.publish(MQTT_AVAILABILITY_TOPIC, "online", retain=True)
        # Publish discovery config for all sensors
        _publish_mqtt_discovery_config()
        # Trigger an immediate sensor update to populate states
        trigger_sensor_update()
    else:
        logger.error(f"Failed to connect to MQTT broker, return code {rc}")
        is_mqtt_connected = False

def on_disconnect(client, userdata, rc, properties=None):
    """Callback for when the client disconnects."""
    global is_mqtt_connected
    is_mqtt_connected = False
    logger.warning(f"Disconnected from MQTT broker. Return code: {rc}")

# --- THIS IS THE FIX ---
# The function signature now correctly includes the 'rc' (reason code) argument,
# matching the 5 arguments passed by the paho-mqtt v2 library.
def on_publish(client, userdata, mid, rc, properties=None):
    """Callback for when a message is published (for debugging)."""
    # We can log the reason code (rc) for more detailed debugging if needed
    logger.debug(f"Published MQTT message with MID: {mid}, RC: {rc}")


# --- NEW MQTT Functions ---
def initialize_mqtt():
    """Initializes and connects the MQTT client."""
    
    # FIX: Defensively check against the string "true" in case configuration loading
    # failed to convert the environment variable string to a proper Python boolean.
    is_mqtt_enabled = config.USE_MQTT_DISCOVERY is True or str(config.USE_MQTT_DISCOVERY).lower() == 'true'
    
    if not is_mqtt_enabled:
        logger.info("MQTT Discovery is disabled in config. Skipping initialization.")
        return

    if not config.MQTT_HOST:
        logger.error("MQTT is enabled but MQTT_HOST is not set. Cannot initialize.")
        return
        
    global mqtt_client
    try:
        # Use MQTTv5
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="wonderful_wino_addon")
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_publish = on_publish

        # Set username and password if provided
        if config.MQTT_USER:
            mqtt_client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)
            
        # Set Last Will and Testament (LWT)
        mqtt_client.will_set(MQTT_AVAILABILITY_TOPIC, payload="offline", retain=True)

        logger.info(f"Connecting to MQTT broker at {config.MQTT_HOST}:{config.MQTT_PORT}...")
        mqtt_client.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
        mqtt_client.loop_start() # Start background thread for network loop
        
    except Exception as e:
        logger.error(f"Error initializing MQTT client: {e}", exc_info=True)

def stop_mqtt():
    """Stops the MQTT client loop and disconnects."""
    global mqtt_client
    if mqtt_client:
        logger.info("Shutting down MQTT client...")
        try:
            # Publish offline message before disconnecting
            mqtt_client.publish(MQTT_AVAILABILITY_TOPIC, "offline", retain=True)
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            logger.info("MQTT client disconnected.")
        except Exception as e:
            logger.error(f"Error during MQTT shutdown: {e}", exc_info=True)

def _publish_mqtt_discovery_config():
    """Publishes the MQTT discovery configuration for all sensors."""
    if not is_mqtt_connected or not mqtt_client:
        logger.warning("Cannot publish MQTT discovery config: not connected.")
        return
        
    logger.info("Publishing MQTT discovery configuration for all sensors...")
    try:
        for sensor_key, sensor_info in SENSOR_DEFINITIONS.items():
            entity_name = sensor_info['name']
            discovery_topic = f"homeassistant/sensor/wonderful_wino/{entity_name}/config"
            state_topic = f"wonderful_wino/sensor/{entity_name}/state"
            
            config_payload = {
                "name": sensor_info['friendly_name'],
                
                # --- NEW FIX ---
                # Explicitly set the object_id to match the 'name' from SENSOR_DEFINITIONS.
                # This ensures the entity_id becomes "sensor.wwino_red_bottles"
                # and prevents HA from auto-generating one from the friendly name.
                "object_id": entity_name,

                # --- NEW FIX 2 ---
                # Set the unique_id to be the same. This is the simplest
                # and cleanest unique ID.
                "unique_id": entity_name,
                
                "state_topic": state_topic,
                "unit_of_measurement": sensor_info['unit'],
                "icon": sensor_info['icon'],
                "device": MQTT_DEVICE_CONFIG,
                "availability_topic": MQTT_AVAILABILITY_TOPIC,
                "payload_available": "online",
                "payload_not_available": "offline"
            }
            
            mqtt_client.publish(discovery_topic, json.dumps(config_payload), retain=True)
            logger.debug(f"Published discovery config for: {entity_name}")
            
        logger.info("Finished publishing MQTT discovery configuration.")
    except Exception as e:
        logger.error(f"Error publishing MQTT discovery config: {e}", exc_info=True)

def publish_stats_to_mqtt(stats: dict):
    """Publishes all inventory statistics to their respective MQTT topics."""
    if not is_mqtt_connected or not mqtt_client:
        logger.warning("Cannot publish stats to MQTT: not connected.")
        return

    logger.debug("Publishing stats to MQTT topics...")
    try:
        for key, sensor_info in SENSOR_DEFINITIONS.items():
            state_value = stats.get(key, 0)
            entity_name = sensor_info['name']
            state_topic = f"wonderful_wino/sensor/{entity_name}/state"
            
            mqtt_client.publish(state_topic, str(state_value), retain=True)
            
        # Also refresh availability
        mqtt_client.publish(MQTT_AVAILABILITY_TOPIC, "online", retain=True)
        logger.debug("Stats and availability published to MQTT.")
        
    except Exception as e:
        logger.error(f"Error publishing stats to MQTT: {e}", exc_info=True)


# --- HA REST API Functions (Original) ---

def _get_ha_headers():
    """Returns the authorization headers for HA API calls."""
    if not config.HA_LONG_LIVED_TOKEN:
        logger.error("Home Assistant Long-Lived Token is not configured.")
        return None
    return {
        "Authorization": f"Bearer {config.HA_LONG_LIVED_TOKEN}",
        "Content-Type": "application/json",
    }

# NOTE: The To-Do List and Event firing MUST use the HA REST API as there is no MQTT equivalent.
# Seeing REST calls here does NOT mean sensor updates are defaulting to REST.

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


# --- HA SENSORS (Original definitions) ---

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
    'unique_red_wines': {
        'name': 'wwino_unique_red_wines',
        'friendly_name': 'Wino Unique Red Wines',
        'unit': 'wines',
        'icon': 'mdi:glass-wine'
    },
    'unique_white_wines': {
        'name': 'wwino_unique_white_wines',
        'friendly_name': 'Wino Unique White Wines',
        'unit': 'wines',
        'icon': 'mdi:glass-wine'
    },
    'unique_sparkling_wines': {
        'name': 'wwino_unique_sparkling_wines',
        'friendly_name': 'Wino Unique Sparkling Wines',
        'unit': 'wines',
        'icon': 'mdi:glass-wine'
    },
    'unique_rose_wines': {
        'name': 'wwino_unique_rose_wines',
        'friendly_name': 'Wino Unique Rosé Wines',
        'unit': 'wines',
        'icon': 'mdi:glass-wine'
    },
    'unique_dessert_wines': {
        'name': 'wwino_unique_dessert_wines',
        'friendly_name': 'Wino Unique Dessert Wines',
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
    (This is the original "ghost" entity method via REST API)
    """
    headers = _get_ha_headers()
    if not headers or not config.HOME_ASSISTANT_URL:
        logger.error("Cannot update HA sensors (REST): Missing URL or Token configuration.")
        return

    logger.debug("Publishing stats to HA via REST API...")
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
            logger.debug(f"Successfully updated HA sensor (REST): {entity_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update HA sensor {entity_id} (REST): {e}")

# --- MODIFIED ROUTER FUNCTION ---

def trigger_sensor_update():
    """
    A single function to fetch statistics and update HA sensors.
    This now acts as a router, deciding *how* to publish based on config.
    """
    try:
        # Add a very short delay to prevent a race condition.
        # This ensures any database commit (e.g., from consume_wine)
        # has finalized before we read the new stats.
        time.sleep(0.5) # Wait 500ms

        stats = db.get_inventory_statistics()
        if not stats:
            logger.warning("Could not retrieve stats to update HA sensors.")
            return
            
        # --- This is the new router logic ---
        # Also check against the string "true" to catch improperly parsed config.
        is_mqtt_enabled = config.USE_MQTT_DISCOVERY is True or str(config.USE_MQTT_DISCOVERY).lower() == 'true'
        
        if is_mqtt_enabled:
            if is_mqtt_connected:
                logger.info("MQTT discovery enabled and connected. Publishing sensor states via MQTT.")
                publish_stats_to_mqtt(stats)
            else:
                # Don't log an error, just a warning. The client might be reconnecting.
                logger.warning("MQTT is enabled but not connected. Skipping sensor update.")
        else:
            # The "old" way
            # Added explicit log to confirm why REST is being used.
            logger.info("MQTT discovery disabled in config. Updating sensors via HA REST API.") 
            update_ha_sensors(stats)
            
    except Exception as e:
        logger.error(f"An unexpected error occurred during trigger_sensor_update: {e}", exc_info=True)