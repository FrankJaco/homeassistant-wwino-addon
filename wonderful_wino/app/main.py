from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/api/health")
def health_check():
    """A simple endpoint to confirm the server is running."""
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)