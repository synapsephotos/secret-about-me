import os
import random
import requests
import asyncio
import threading
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncioScheduler

# --- Flask Setup (For Keep-Alive) ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "presence": "invisible",
        "recent_updates": update_history,
        "config": {
            "target_time": "05:55",
            "timezone": "Europe/Paris",
            "jitter_range": "555-3655s"
        }
    }), 200

def run_flask():
    # Listens on port 5000 (standard for Flask)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- Logic Functions ---

def prepare_for_reverse(text: str) -> str:
    if not text: return ""
    text = text.replace(", ", " ,")
    chars_to_move = ".?!"
    stripped_text = text.rstrip(chars_to_move)
    punctuation_tail = text[len(stripped_text):]
    return punctuation_tail + stripped_text

def vigenere_encrypt(plaintext: str, key: str) -> str:
    if not key: return plaintext
    key = "".join(filter(str.isalpha, key)).upper()
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

# --- Discord Self-Bot & Scheduler ---

class MySelfBot(commands.Bot):
    def __init__(self):
        # Initializing with status=invisible prevents the "online flicker"
        super().__init__(
            command_prefix="!", 
            self_bot=True,
            status=discord.Status.invisible
        )
        self.scheduler = AsyncioScheduler()

    async def on_ready(self):
        print(f'--- Logged in as {self.user} ---')
        print(f'--- Status set to: {self.status} ---')
        
        # Start the scheduler inside the async loop
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.daily_update_job, 
                'cron', 
                hour=5, 
                minute=55, 
                timezone=timezone('Europe/Paris')
            )
            self.scheduler.start()
            print("[Scheduler] Active: Targeting 05:55 Europe/Paris daily.")

    async def daily_update_job(self):
        # Your custom jitter: ~9 mins to 1 hour
        jitter = random.randint(555, 3655)
        print(f"Update triggered! Applying jitter: Waiting {jitter} seconds...")
        await asyncio.sleep(jitter)
        
        try:
            # 1. Fetching Data
            template_resp = requests.get("https://kirenity.ct8.pl/55.json", timeout=10).json()
            template = template_resp.get("template", "{SECRET_TEXT}")
            
            quotes = requests.get("https://kirenity.ct8.pl/5.json", timeout=10).json()
            original = random.choice(quotes) if quotes else "Default message"
            
            # 2. Cryptography Logic
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY"))
            # Reversed and lowercased as per your original logic
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            # 3. Apply via discord.py-self
            await self.user.edit(bio=new_bio)
            
            # 4. Success Logging for Flask
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {
                "time": now_str, 
                "original": original, 
                "result": new_bio,
                "jitter_used": f"{jitter}s"
            })
            if len(update_history) > 5: update_history.pop()
            print(f"[{now_str}] Bio successfully updated.")

        except Exception as e:
            print(f"[Error] Update failed: {e}")

# --- Execution ---

if __name__ == "__main__":
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Run the Bot
    token = os.getenv("USER_TOKEN")
    if token:
        bot = MySelfBot()
        bot.run(token)
    else:
        print("[Critical] No USER_TOKEN found in environment variables!")
