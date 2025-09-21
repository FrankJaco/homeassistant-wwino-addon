import logging
from flask import Flask, jsonify
from flask_cors import CORS
from . import config, db # Import the new config and db modules

# Get the logger from the config file
logger = logging.getLogger(__name__)

# --- Flask App Setup ---
app = Flask(__name__, static_folder="../../frontend", static_url_path="")
CORS(app)

# --- Flask WSGI Middleware for Home Assistant Ingress ---
# This class helps Flask understand that it's running behind a proxy
# (Home Assistant's ingress) and that its URLs should be prefixed.
class ReverseProxied:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Home Assistant's ingress typically sets X-Forwarded-Prefix
        script_name = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            # Adjust PATH_INFO to be relative to SCRIPT_NAME
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]
        # Also handle X-Forwarded-Proto for HTTPS
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

app.wsgi_app = ReverseProxied(app.wsgi_app)

# --- Routes ---
@app.route("/api/health")
def health_check():
    """A simple endpoint to confirm the server is running."""
    logger.info("Health check endpoint was called.")
    return jsonify({"status": "ok"})

# Your other routes will be added here later...

# --- Main Execution ---
if __name__ == '__main__':
    db.init_db() # Initialize the database on startup
    logger.info(f"Starting Wonderful Wino on port 5000 with log level {config.LOG_LEVEL}")
    app.run(host='0.0.0.0', port=5000)
