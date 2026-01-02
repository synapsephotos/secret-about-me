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

# --- Flask Setup ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot_connected": bot.is_ready(),
        "recent_updates": update_history,
        "config": {"target_time": "05:55", "timezone": "Europe/Paris"}
    }), 200

@app.route('/update')
def manual_update():
    """Route to manually trigger the update for testing."""
    print("[Manual] Trigger received via web request.")
    asyncio.run_coroutine_threadsafe(bot.run_daily_update(), bot.loop)
    return jsonify({"message": "Update task sent to bot loop"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Cryptography Logic ---

def prepare_for_reverse(text: str) -> str:
    if not text: return ""
    text = text.replace(", ", " ,")
    chars_to_move = ".?!\""
    stripped_text = text.rstrip(chars_to_move)
    return text[len(stripped_text):] + stripped_text

def vigenere_encrypt(plaintext: str, key: str) -> str:
    if not key: return plaintext
    key = "".join(filter(str.isalpha, key)).upper()
    ciphertext = []
    key_len, key_idx = len(key), 0
    for char in plaintext:
        if char.isalpha():
            base = ord('a') if char.islower() else ord('A')
            p_shift = ord(char.upper()) - ord('A')
            k_shift = ord(key[key_idx % key_len]) - ord('A')
            ciphertext.append(chr((p_shift + k_shift) % 26 + base))
            key_idx += 1
        else:
            ciphertext.append(char)
    return "".join(ciphertext)

# --- Discord Bot ---

class MySelfBot(discord.Client):
    async def on_ready(self):
        # Even if this never prints, the scheduler will still work now
        print(f'--- Bot is online as {self.user} ---')
        await self.change_presence(afk=True)

    async def run_daily_update(self):
        """The actual task logic."""
        # Use a small sleep for safety, remove jitter for manual testing if needed
        print("[Task] Starting bio update sequence...")
        
        try:
            # 1. Fetching
            t_resp = requests.get("https://kirenity.ct8.pl/55.json", timeout=10).json()
            template = t_resp.get("template", "{SECRET_TEXT}")
            
            q_resp = requests.get("https://kirenity.ct8.pl/5.json", timeout=10).json()
            original = random.choice(q_resp) if q_resp else "Shiny Lunala"
            
            # 2. Cryptography
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY", "KEY"))
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            # 3. Apply
            await self.user.edit(bio=new_bio)
            
            # 4. Log
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {"time": now_str, "result": new_bio})
            print(f"[{now_str}] Bio updated successfully.")
        except Exception as e:
            print(f"[Error] Task failed: {e}")

bot = MySelfBot(chunk_guilds_at_startup=False)

# --- Scheduler Setup ---

def scheduler_bridge():
    """Triggered by APScheduler thread, safely injects into Discord's Async loop."""
    print("[Scheduler] 05:55 hit. Injecting update task...")
    asyncio.run_coroutine_threadsafe(bot.run_daily_update(), bot.loop)

scheduler = BackgroundScheduler(timezone=timezone('Europe/Paris'))
scheduler.add_job(scheduler_bridge, 'cron', hour=5, minute=55)

# --- Main Execution ---

if __name__ == "__main__":
    # Start Flask first
    threading.Thread(target=run_flask, daemon=True).start()

    # Start Scheduler second
    scheduler.start()
    print("[System] Background Scheduler Active: Targeting 05:55 Daily.")

    # Run Bot (Blocking)
    token = os.getenv("USER_TOKEN")
    if token:
        bot.run(token)
    else:
        print("CRITICAL: No USER_TOKEN provided.")
