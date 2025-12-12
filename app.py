import os
import random
import requests
import json
from datetime import datetime
import time
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# --- Flask Setup ---
app = Flask(__name__)

# --- Configuration ---
USER_TOKEN = os.getenv("USER_TOKEN")
VIGENERE_KEY = os.getenv("VIGENERE_KEY")
QUOTES_JSON_URL = "https://kirenity.ct8.pl/5.json"
BIO_TEMPLATE_URL = "https://kirenity.ct8.pl/55.json"

TARGET_TIMEZONE = 'Europe/Paris'
UPDATE_HOUR = 5
UPDATE_MINUTE = 55

# --- Helper Functions ---

def vigenere_encrypt(plaintext: str, key: str) -> str:
    """Encrypts plaintext using the Vigenere Cipher."""
    key = "".join(filter(str.isalpha, key)).upper()
    if not plaintext or not key: return ""
    ciphertext = []
    key_len, key_idx = len(key), 0
    for char in plaintext:
        if char.isalpha():
            is_lower = char.islower()
            base = ord('a') if is_lower else ord('A')
            plain_shift = ord(char.upper()) - ord('A')
            key_shift = ord(key[key_idx % key_len]) - ord('A')
            cipher_shift = (plain_shift + key_shift) % 26
            ciphertext.append(chr(cipher_shift + base))
            key_idx += 1
        else:
            ciphertext.append(char)
    return "".join(ciphertext)

def reverse_string(text: str) -> str:
    return text[::-1]

def fetch_quotes(url: str) -> list:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[-] Quote Fetch Error: {e}")
        return []

def fetch_bio_template(url: str) -> str | None:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get("template")
    except Exception as e:
        print(f"[-] Template Fetch Error: {e}")
        return None

def update_discord_about_me(new_bio: str):
    url = "https://discord.com/api/v10/users/@me"
    headers = {"Authorization": USER_TOKEN, "Content-Type": "application/json"}
    try:
        response = requests.patch(url, json={"bio": new_bio}, headers=headers)
        if response.status_code == 200:
            print("[OK] Discord Bio Updated!")
        else:
            print(f"[X] Discord Error: {response.status_code}")
    except Exception as e:
        print(f"[-] API Request Error: {e}")

def daily_update_job():
    print(f"[{datetime.now()}] Starting scheduled update...")
    template = fetch_bio_template(BIO_TEMPLATE_URL) or "Secret: {SECRET_TEXT}"
    quotes = fetch_quotes(QUOTES_JSON_URL)
    
    selected = random.choice(quotes) if quotes else "Default message"
    encrypted = vigenere_encrypt(selected, VIGENERE_KEY)
    final_text = reverse_string(encrypted).lower()
    
    new_bio = template.format(SECRET_TEXT=final_text)
    update_discord_about_me(new_bio)

# --- Flask Routes ---

@app.route('/')
def home():
    return {"status": "running", "timezone": TARGET_TIMEZONE, "next_update": f"{UPDATE_HOUR}:{UPDATE_MINUTE}"}, 200

# --- Scheduler Initialization ---

scheduler = BackgroundScheduler(timezone='UTC')
scheduler.add_job(
    daily_update_job, 
    'cron', 
    hour=UPDATE_HOUR, 
    minute=UPDATE_MINUTE, 
    timezone=timezone(TARGET_TIMEZONE)
)
scheduler.start()

if __name__ == "__main__":
    # Render provides a PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
