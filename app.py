import os
import random
import requests
import asyncio
import threading
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncioScheduler

# --- Flask Setup (For Keep-Alive) ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot_user": "Active",
        "recent_updates": update_history
    }), 200

def run_flask():
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
    v_key = os.getenv("VIGENERE_KEY")
    if not v_key: return plaintext
    v_key = "".join(filter(str.isalpha, v_key)).upper()
    ciphertext = []
    key_len, key_idx = len(v_key), 0
    for char in plaintext:
        if char.isalpha():
            is_lower = char.islower()
            base = ord('a') if is_lower else ord('A')
            plain_shift = ord(char.upper()) - ord('A')
            key_shift = ord(v_key[key_idx % key_len]) - ord('A')
            cipher_shift = (plain_shift + key_shift) % 26
            ciphertext.append(chr(cipher_shift + base))
            key_idx += 1
        else:
            ciphertext.append(char)
    return "".join(ciphertext)

# --- Discord Self-Bot & Scheduler ---

class MySelfBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", self_bot=True)
        self.scheduler = AsyncioScheduler()

    async def on_ready(self):
        print(f'--- Logged in as {self.user} ---')
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.daily_update_job, 
                'cron', 
                hour=5, 
                minute=55, 
                timezone=timezone('Europe/Paris')
            )
            self.scheduler.start()

    async def daily_update_job(self):
        await asyncio.sleep(random.randint(555, 3655)) # Anti-detection jitter
        try:
            # 1. Fetch
            template_resp = requests.get("https://kirenity.ct8.pl/55.json", timeout=10).json()
            template = template_resp.get("template", "{SECRET_TEXT}")
            quotes = requests.get("https://kirenity.ct8.pl/5.json", timeout=10).json()
            original = random.choice(quotes)
            
            # 2. Process
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY"))
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            # 3. Apply
            await self.user.edit(bio=new_bio)
            
            # 4. Log for Flask route
            update_history.insert(0, {"time": datetime.now().isoformat(), "bio": new_bio})
            if len(update_history) > 5: update_history.pop()
            print(f"[OK] Bio updated: {new_bio}")

        except Exception as e:
            print(f"[Error] Update failed: {e}")

# --- Execution ---

if __name__ == "__main__":
    # Start Flask in a separate thread so it doesn't block the Bot
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # Start the Bot
    bot = MySelfBot()
    bot.run(os.getenv("USER_TOKEN"))
