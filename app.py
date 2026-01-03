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

# --- Flask Setup (Corrected) ---
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
    # Render requires port 10000 by default or the $PORT env var
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Logic Functions (unchanged) ---
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
        else: ciphertext.append(char)
    return "".join(ciphertext)

# --- Force Mobile Identity (Required for Self-Bots) ---
# This prevents Discord from immediately flagging the login as a "headless bot"
discord.client.ConnectionState.identify_properties = lambda self: {
    '$os': 'iOS',
    '$browser': 'Discord iOS',
    '$device': 'iPhone'
}

# --- Discord Self-Bot & Scheduler ---
class MySelfBot(discord.Client):
    def __init__(self):
        # Disable chunking to make on_ready fire faster
        super().__init__(chunk_guilds_at_startup=False)
        self.scheduler = AsyncIOScheduler()
        
    async def on_ready(self):
        print(f'--- Logged in as {self.user} ---')
        # Use self instead of global 'bot' to avoid NameErrors
        await self.change_presence(afk=True)
        
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
        jitter = random.randint(555, 3655)
        print(f"Update triggered! Waiting {jitter} seconds...")
        await asyncio.sleep(jitter)
        
        try:
            # Note: Using requests inside an async function is "blocking."
            # For 1 task a day, it's fine, but aiohttp is better for scale.
            template_resp = requests.get("https://kirenity.ct8.pl/55.json", timeout=10).json()
            template = template_resp.get("template", "{SECRET_TEXT}")
            
            quotes = requests.get("https://kirenity.ct8.pl/5.json", timeout=10).json()
            original = random.choice(quotes) if quotes else "Shiny Lunala"
            
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY"))
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            await self.user.edit(bio=new_bio)
            
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {"time": now_str, "result": new_bio})
            print(f"[{now_str}] Bio successfully updated.")

        except Exception as e:
            print(f"[Error] Update failed: {e}")

# --- Execution ---
if __name__ == "__main__":
    # 1. Start Flask Thread FIRST
    keep_alive()

    # 2. Run Bot (BLOCKING CALL)
    token = os.getenv("USER_TOKEN")
    if token:
        bot = MySelfBot()
        bot.run(token)
    else:
        print("[Critical] No USER_TOKEN found!")
