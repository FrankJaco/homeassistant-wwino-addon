#!/usr/bin/with-contenv bashio

echo "Starting Wine Inventory Scanner Addon..."

# Export config values as environment variables for the Python app
export HOME_ASSISTANT_URL=$(bashio::config 'HOME_ASSISTANT_URL')
export HA_LONG_LIVED_TOKEN=$(bashio::config 'HA_LONG_LIVED_TOKEN')
export TODO_LIST_ENTITY_ID=$(bashio::config 'TODO_LIST_ENTITY_ID')
export LOG_LEVEL=$(bashio::config 'LOG_LEVEL')

exec python3 /app/WW-main.py

