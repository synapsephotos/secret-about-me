import os
import random
import requests
import json
from datetime import datetime
import time
from flask import Flask, jsonify
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

# Global variable to track recent activity
update_history = []

# --- Helper Functions ---

def prepare_for_reverse(text: str) -> str:
    """Rearranges punctuation to land correctly after reversing."""
    if not text: return ""
    # Swap ", " to " ," so reverse produces ", "
    text = text.replace(", ", " ,")
    # Move trailing punctuation to the front
    punctuation_marks = ('.', '?', '!')
    if text.endswith(punctuation_marks):
        return text[-1] + text[:-1]
    return text

def vigenere_encrypt(plaintext: str, key: str) -> str:
    """Encrypts plaintext using the Vigenere Cipher."""
    if not VIGENERE_KEY: return plaintext # Fallback if env var missing
    key = "".join(filter(str.isalpha, key)).upper()
    if not plaintext or not key: return plaintext
    
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
    if not USER_TOKEN:
        print("[!] No USER_TOKEN found in environment variables.")
        return
    url = "https://discord.com/api/v10/users/@me"
    headers = {"Authorization": USER_TOKEN, "Content-Type": "application/json"}
    try:
        response = requests.patch(url, json={"bio": new_bio}, headers=headers)
        if response.status_code == 200:
            print("[OK] Discord Bio Updated!")
        else:
            print(f"[X] Discord Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[-] API Request Error: {e}")

def daily_update_job():
    now = datetime.now(timezone(TARGET_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Starting scheduled update...")
    
    # 1. Fetch
    template = fetch_bio_template(BIO_TEMPLATE_URL) or "Secret: {SECRET_TEXT}"
    quotes = fetch_quotes(QUOTES_JSON_URL)
    original = random.choice(quotes) if quotes else "Default message"
    
    # 2. Logic Flow: Prepare -> Encrypt -> Reverse
    prepared = prepare_for_reverse(original)
    encrypted = vigenere_encrypt(prepared, VIGENERE_KEY)
    final_text = reverse_string(encrypted).lower()
    
    new_bio = template.format(SECRET_TEXT=final_text)
    
    # 3. Apply
    update_discord_about_me(new_bio)
    
    # 4. Log to history
    update_history.insert(0, {
        "time": now,
        "original": original,
        "result": new_bio
    })
    if len(update_history) > 5: update_history.pop()

# --- Flask Routes ---

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "timezone": TARGET_TIMEZONE,
        "next_scheduled_at": f"{UPDATE_HOUR:02d}:{UPDATE_MINUTE:02d}",
        "recent_updates": update_history
    }), 200

# --- Scheduler Initialization ---

scheduler = BackgroundScheduler()
scheduler.add_job(
    daily_update_job, 
    'cron', 
    hour=UPDATE_HOUR, 
    minute=UPDATE_MINUTE, 
    timezone=timezone(TARGET_TIMEZONE)
)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Note: use_reloader=False prevents the scheduler from starting twice
    app.run(host='0.0.0.0', port=port, use_reloader=False)
