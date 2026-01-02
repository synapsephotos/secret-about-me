import os
import random
import aiohttp
import asyncio
import threading
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Flask Setup ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({"status": "running", "history": update_history}), 200

def run_flask():
    # Adding a try-except here to see if Flask is crashing
    try:
        port = int(os.environ.get("PORT", 5000))
        print(f"[Flask] Starting on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[Flask Error] {e}")

# --- Cryptography Logic ---
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

# --- Discord Self-Bot ---
class MySelfBot(commands.Bot):
    def __init__(self):
        # Explicitly setting intents to minimal for a self-bot
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!", 
            self_bot=True,
            status=discord.Status.invisible,
            intents=intents,
            chunk_guilds_at_startup = False
        )
        self.scheduler = AsyncIOScheduler()

    async def setup_hook(self):
        # We start the scheduler here as it's the first async entry point
        print("DEBUG: Entering setup_hook...")
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.daily_update_job, 
                'cron', 
                hour=5, 
                minute=55, 
                timezone=timezone('Europe/Paris')
            )
            self.scheduler.start()
            print("[Scheduler] SUCCESS: Targeting 05:55 Europe/Paris daily.")

    async def on_ready(self):
        # Force invisible/afk again on connection
        await self.change_presence(status=discord.Status.invisible, afk=True)
        print(f'--- LOGGED IN: {self.user} ---')

    async def daily_update_job(self):
        jitter = random.randint(555, 3655)
        print(f"Update triggered. Jitter: {jitter}s")
        await asyncio.sleep(jitter)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://kirenity.ct8.pl/55.json") as r:
                    template = (await r.json()).get("template", "{SECRET_TEXT}")
                async with session.get("https://kirenity.ct8.pl/5.json") as r:
                    quotes = await r.json()
                    original = random.choice(quotes)
            
            final_text = vigenere_encrypt(prepare_for_reverse(original), os.getenv("VIGENERE_KEY"))[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            await self.user.edit(bio=new_bio)
            print(f"Bio updated at {datetime.now()}")
            update_history.insert(0, {"time": str(datetime.now()), "bio": new_bio})
        except Exception as e:
            print(f"Job Error: {e}")

# --- Main Boot Sequence ---
if __name__ == "__main__":
    print("DEBUG: Script started.")
    
    # 1. Start Flask first
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    print("DEBUG: Flask thread spawned.")

    # 2. Check Token
    token = os.getenv("USER_TOKEN")
    if not token:
        print("[CRITICAL] USER_TOKEN is missing!")
    else:
        # 3. Start Bot
        bot = MySelfBot()
        try:
            print("DEBUG: Attempting bot.run()...")
            bot.run(token)
        except Exception as e:
            print(f"[CRITICAL] Bot crashed: {e}")
