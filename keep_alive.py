from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

# This function handles the actual web request
@app.route('/')
def home():
    return "Bot is alive!", 200

def run():
    # Render uses the 'PORT' environment variable; 10000 is the default fallback
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True  # Allows the thread to exit when the main script stops
    t.start()