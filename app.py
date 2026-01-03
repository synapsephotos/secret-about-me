import os
import random
import asyncio
import threading
import aiohttp
import discord
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify

# --- Flask Setup ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({"status": "online", "history": update_history}), 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Logic Functions ---
def prepare_for_reverse(text: str) -> str:
    if not text: return ""
    text = text.replace(", ", " ,")
    stripped = text.rstrip(".?!\"")
    return text[len(stripped):] + stripped

def vigenere_encrypt(plaintext: str, key: str) -> str:
    if not key: return plaintext
    key = "".join(filter(str.isalpha, key)).upper()
    ciphertext, key_len, key_idx = [], len(key), 0
    for char in plaintext:
        if char.isalpha():
            base = ord('a') if char.islower() else ord('A')
            shift = (ord(char.upper()) - ord('A') + ord(key[key_idx % key_len]) - ord('A')) % 26
            ciphertext.append(chr(shift + base))
            key_idx += 1
        else:
            ciphertext.append(char)
    return "".join(ciphertext)

# --- Discord Identity Patch ---
discord.client.ConnectionState.identify_properties = lambda self: {
    '$os': 'iOS', '$browser': 'Discord iOS', '$device': 'iPhone'
}

class MySelfBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, chunk_guilds_at_startup=False)
        self.target_hour = 5
        self.target_minute = 55

    async def setup_hook(self):
        # This starts the background task properly in the discord loop
        self.loop.create_task(self.daily_loop())

    async def on_ready(self):
        print(f'--- DEFINITIVE SUCCESS: Logged in as {self.user} ---')
        await self.change_presence(afk=True)

    async def daily_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            tz = timezone('Europe/Paris')
            now = datetime.now(tz)
            
            # Calculate seconds until 05:55
            target = now.replace(hour=self.target_hour, minute=self.target_minute, second=0, microsecond=0)
            if now >= target:
                target = target.replace(day=now.day + 1)
            
            wait_seconds = (target - now).total_seconds()
            print(f"Next update in {wait_seconds} seconds.")
            await asyncio.sleep(wait_seconds)
            
            # Jitter: 9m to 1h
            await asyncio.sleep(random.randint(555, 3655))
            await self.execute_update()

    async def execute_update(self):
        print("Executing Bio Update...")
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch Template
                async with session.get("https://kirenity.ct8.pl/55.json") as r:
                    t_data = await r.json()
                    template = t_data.get("template", "{SECRET_TEXT}")
                
                # Fetch Quotes
                async with session.get("https://kirenity.ct8.pl/5.json") as r:
                    q_data = await r.json()
                    original = random.choice(q_data) if q_data else "Shiny Lunala"

            # Cryptography
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY"))
            final_bio = template.format(SECRET_TEXT=encrypted[::-1].lower())

            await self.user.edit(bio=final_bio)
            
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {"time": now_str, "result": final_bio})
            print(f"SUCCESS: Bio updated at {now_str}")
        except Exception as e:
            print(f"UPDATE ERROR: {e}")

# --- Execution ---
if __name__ == "__main__":
    # 1. Background Web Server
    threading.Thread(target=run_flask, daemon=True).start()

    # 2. Start Bot
    token = os.getenv("USER_TOKEN")
    if token:
        bot = MySelfBot()
        bot.run(token)
    else:
        print("TOKEN MISSING")