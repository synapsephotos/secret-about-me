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
    return jsonify({
        "status": "online",
        "presence": "invisible",
        "recent_updates": update_history,
        "config": {"target_time": "05:55", "timezone": "Europe/Paris"}
    }), 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- Logic Functions ---

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
        super().__init__(
            command_prefix="!", 
            self_bot=True,
            status=discord.Status.invisible  # Force invisible from start
        )
        self.scheduler = AsyncIOScheduler()

    async def setup_hook(self):
        """This runs before the bot logs in."""
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.daily_update_job, 
                'cron', 
                hour=5, 
                minute=55, 
                timezone=timezone('Europe/Paris')
            )
            self.scheduler.start()
            print("[Scheduler] Started: Targeting 05:55 Europe/Paris daily.")

    async def on_ready(self):
        # We set AFK here just to be sure
        await self.change_presence(status=discord.Status.invisible, afk=True)
        print(f'--- Logged in as {self.user} (Invisible/AFK) ---')

    async def daily_update_job(self):
        jitter = random.randint(555, 3655)
        print(f"Update triggered! Waiting {jitter}s jitter...")
        await asyncio.sleep(jitter)
        
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Fetch Template
                async with session.get("https://kirenity.ct8.pl/55.json") as r:
                    template_data = await r.json()
                    template = template_data.get("template", "{SECRET_TEXT}")
                
                # 2. Fetch Quotes
                async with session.get("https://kirenity.ct8.pl/5.json") as r:
                    quotes = await r.json()
                    original = random.choice(quotes) if quotes else "Default message"

            # 3. Processing
            prepared = prepare_for_reverse(original)
            encrypted = vigenere_encrypt(prepared, os.getenv("VIGENERE_KEY"))
            final_text = encrypted[::-1].lower()
            new_bio = template.format(SECRET_TEXT=final_text)

            # 4. Update Profile
            await self.user.edit(bio=new_bio)
            
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {"time": now_str, "original": original, "jitter": f"{jitter}s"})
            if len(update_history) > 5: update_history.pop()
            print(f"[{now_str}] Bio updated successfully.")

        except Exception as e:
            print(f"[Error] Update failed: {e}")

# --- Execution ---

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    token = os.getenv("USER_TOKEN")
    if token:
        bot = MySelfBot()
        try:
            bot.run(token)
        except Exception as e:
            print(f"[Critical] Bot failed to start: {e}")
    else:
        print("[Critical] No USER_TOKEN found!")
