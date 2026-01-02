import os
import random
import requests
import asyncio
import threading
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
import discord
from apscheduler.schedulers.background import BackgroundScheduler

# --- Flask Setup (For Render Keep-Alive) ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "recent_updates": update_history,
        "config": {
            "target_time": "05:55",
            "timezone": "Europe/Paris",
            "jitter_range": "555-3655s"
        }
    }), 200

def run_flask():
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Cryptography & Logic ---

def prepare_for_reverse(text: str) -> str:
    if not text: return ""
    text = text.replace(", ", " ,")
    chars_to_move = ".?!\""
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

# --- Discord Bot Class ---

class MySelfBot(discord.Client):
    def __init__(self, **options):
        super().__init__(**options)

    async def on_ready(self):
        print(f'--- Logged in as {self.user} (ID: {self.user.id}) ---')
        await self.change_presence(afk=True)

    async def run_daily_update(self):
        """The actual update logic called by the scheduler."""
        jitter = random.randint(555, 3655)
        print(f"[Scheduler] Triggered! Applying jitter: {jitter}s...")
        await asyncio.sleep(jitter)
        
        try:
            # 1. Fetching Data
            template_resp = requests.get("https://kirenity.ct8.pl/55.json", timeout=10).json()
            template = template_resp.get("template", "{SECRET_TEXT}")
            
            quotes = requests.get("https://kirenity.ct8.pl/5.json", timeout=10).json()
            original = random.choice(quotes) if quotes else "Shiny Lunala"
            
            # 2. Logic
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY", "DEFAULT"))
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            # 3. Apply Update
            await self.user.edit(bio=new_bio)
            
            # 4. Success Logging
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

# --- Background Scheduler Bridge ---

bot = MySelfBot(chunk_guilds_at_startup=False)
scheduler = BackgroundScheduler(timezone=timezone('Europe/Paris'))

def scheduler_job_bridge():
    """Bridges the threaded scheduler to the Discord async event loop."""
    print("[Scheduler] It is 05:55! Sending task to Discord loop...")
    if bot.is_ready():
        asyncio.run_coroutine_threadsafe(bot.run_daily_update(), bot.loop)
    else:
        print("[Scheduler Error] Bot is not connected. Skipping update.")

# --- Execution Block ---

if __name__ == "__main__":
    # 1. Start Flask in background
    print("[System] Starting Flask keep-alive thread...")
    threading.Thread(target=run_flask, daemon=True).start()

    # 2. Configure and Start Scheduler BEFORE bot blocks the main thread
    print("[System] Starting Background Scheduler...")
    scheduler.add_job(scheduler_job_bridge, 'cron', hour=5, minute=55)
    scheduler.start()

    # 3. Run the Discord Bot
    token = os.getenv("USER_TOKEN")
    if token:
        try:
            bot.run(token)
        except Exception as e:
            print(f"[Critical] Discord login failed: {e}")
    else:
        print("[Critical] No USER_TOKEN found in environment variables!")
