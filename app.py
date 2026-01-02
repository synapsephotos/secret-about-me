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
        "recent_updates": update_history,
        "config": {"target_time": "05:55", "timezone": "Europe/Paris"}
    }), 200

def run_flask():
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
    ciphertext = []
    key_len, key_idx = len(key), 0
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

# --- Discord Bot & Scheduler ---
class MySelfBot(discord.Client):
    async def on_ready(self):
        print(f'--- Logged in as {self.user} ---')
        await self.change_presence(afk=True)

    async def daily_update_job(self):
        jitter = random.randint(555, 3655)
        print(f"Update triggered! Waiting {jitter}s jitter...")
        await asyncio.sleep(jitter)
        
        try:
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
            update_history.insert(0, {"time": now_str, "original": original, "result": new_bio})
            print(f"[{now_str}] Bio updated.")
        except Exception as e:
            print(f"[Error] Update failed: {e}")

bot = MySelfBot(chunk_guilds_at_startup=False)

# --- The "Universal" Scheduler Fix ---
# We use BackgroundScheduler because it runs in its own thread and doesn't depend on Discord's loop
scheduler = BackgroundScheduler(timezone=timezone('Europe/Paris'))

def scheduler_bridge():
    """Bridges the threaded scheduler to the Discord async loop."""
    print("[Scheduler] Cron tick reached. Injecting task into Discord loop...")
    asyncio.run_coroutine_threadsafe(bot.daily_update_job(), bot.loop)

# --- Execution ---
if __name__ == "__main__":
    # 1. Start Flask
    threading.Thread(target=run_flask, daemon=True).start()

    # 2. Start Scheduler immediately
    scheduler.add_job(scheduler_bridge, 'cron', hour=5, minute=55)
    scheduler.start()
    print("[Scheduler] Started and waiting for 05:55.")

    # 3. Run Bot
    token = os.getenv("USER_TOKEN")
    if token:
        bot.run(token)
    else:
        print("No USER_TOKEN found!")
