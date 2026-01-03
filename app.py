import os
import random
import requests
import asyncio
import threading
import logging
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Flask Setup ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "recent_updates": update_history,
        "config": {"target_time": "05:55", "timezone": "Europe/Paris"}
    }), 200

def run_flask():
    # Render requires port 10000 or the $PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Logic Functions ---
def prepare_for_reverse(text: str) -> str:
    if not text: return ""
    text = text.replace(", ", " ,")
    chars_to_move = ".?!\""
    stripped_text = text.rstrip(chars_to_move)
    return text[len(stripped_text):] + stripped_text

def vigenere_encrypt(plaintext: str, key: str) -> str:
    if not key: return plaintext
    key = "".join(filter(str.isalpha, key)).upper()
    ciphertext, key_len, key_idx = [], len(key), 0
    for char in plaintext:
        if char.isalpha():
            base = ord('a') if char.islower() else ord('A')
            plain_shift = ord(char.upper()) - ord('A')
            key_shift = ord(key[key_idx % key_len]) - ord('A')
            ciphertext.append(chr((plain_shift + key_shift) % 26 + base))
            key_idx += 1
        else:
            ciphertext.append(char)
    return "".join(ciphertext)

# --- Force Mobile Identity ---
# Essential for self-bots to prevent connection drops
discord.client.ConnectionState.identify_properties = lambda self: {
    '$os': 'iOS',
    '$browser': 'Discord iOS',
    '$device': 'iPhone'
}

# --- Discord Self-Bot & Scheduler ---
class MySelfBot(discord.Client):
    def __init__(self):
        # We use optimized settings to avoid the 'on_ready' deadlock
        super().__init__(
            chunk_guilds_at_startup=False,
            heartbeat_timeout=60.0,
            guild_ready_timeout=5.0
        )
        self.scheduler = AsyncIOScheduler()
        self.startup_done = False 

    async def on_connect(self):
        """Fires as soon as the bot touches the gateway, bypassing the Ready hang."""
        if self.startup_done:
            return

        print(f"--- SYSTEM: Gateway Connected. User: {self.user} ---")
        
        try:
            await self.change_presence(afk=True)
            print("--- SYSTEM: Presence set to AFK ---")
        except:
            pass
        
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
        
        self.startup_done = True
        print("--- SUCCESS: Bot logic is now running ---")

    async def daily_update_job(self):
        jitter = random.randint(555, 3655)
        print(f"Update triggered! Applying jitter: Waiting {jitter} seconds...")
        await asyncio.sleep(jitter)
        
        try:
            # 1. Fetching Data
            template_resp = requests.get("https://kirenity.ct8.pl/55.json", timeout=15).json()
            template = template_resp.get("template", "{SECRET_TEXT}")
            
            quotes = requests.get("https://kirenity.ct8.pl/5.json", timeout=15).json()
            original = random.choice(quotes) if quotes else "Shiny Lunala"
            
            # 2. Cryptography Logic
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY"))
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            # 3. Apply via discord.py
            await self.user.edit(bio=new_bio)
            
            # 4. Success Logging
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {"time": now_str, "result": new_bio})
            if len(update_history) > 5: update_history.pop()
            print(f"[{now_str}] Bio successfully updated.")

        except Exception as e:
            print(f"[Error] Update failed: {e}")

# --- Execution ---
if __name__ == "__main__":
    # Start Flask in a background thread to satisfy Render's port check
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Run the Bot
    token = os.getenv("USER_TOKEN")
    if token:
        bot = MySelfBot()
        try:
            bot.run(token)
        except Exception as e:
            print(f"[Critical] Bot failed to start: {e}")
    else:
        print("[Critical] No USER_TOKEN found in environment variables!")