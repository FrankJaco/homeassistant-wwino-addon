import os
import logging

def str_to_bool(val):
    """Converts an environment variable to a proper boolean."""
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in ("true", "1", "yes", "y", "on")

# --- Configuration (read from environment variables) ---
HOME_ASSISTANT_URL = os.environ.get("HOME_ASSISTANT_URL")
HA_LONG_LIVED_TOKEN = os.environ.get("HA_LONG_LIVED_TOKEN")
TODO_LIST_ENTITY_ID = os.environ.get("TODO_LIST_ENTITY_ID")
DB_PATH = os.environ.get("DB_PATH", "/share/wwino/wine_inventory.db")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# --- NEW MQTT Configuration ---
USE_MQTT_DISCOVERY = str_to_bool(os.environ.get("USE_MQTT_DISCOVERY", "false"))
MQTT_HOST = os.environ.get("MQTT_HOST")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")


# --- Create Database Directory ---
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
