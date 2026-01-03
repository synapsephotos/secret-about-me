import os
import random
import requests
import asyncio
import threading
import logging
import json
from datetime import datetime
from pytz import timezone
from flask import Flask, jsonify
import discord
from discord.ext import tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Flask Setup ---
app = Flask(__name__)
update_history = []

@app.route('/')
def home():
    return jsonify({"status": "active", "history": update_history}), 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Force Mobile Identity ---
discord.client.ConnectionState.identify_properties = lambda self: {
    '$os': 'iOS', '$browser': 'Discord iOS', '$device': 'iPhone'
}

class MySelfBot(discord.Client):
    def __init__(self):
        super().__init__(
            chunk_guilds_at_startup=False,
            heartbeat_timeout=60.0,
            guild_ready_timeout=5.0
        )
        self.scheduler = AsyncIOScheduler()
        self.startup_done = False 

    # RAW SOCKET LISTENER: This fires even if the library is frozen
    async def on_socket_raw_receive(self, msg):
        if self.startup_done:
            return
            
        # Check if the raw message from Discord is the 'READY' event
        if isinstance(msg, str) and '"t":"READY"' in msg:
            print("--- DEBUG: RAW READY PACKET DETECTED ---")
            await self.force_start_logic()

    async def on_connect(self):
        print("--- DEBUG: Socket Connected to Gateway ---")
        # Safety net: If READY packet isn't caught in 15s, force start anyway
        await asyncio.sleep(15)
        if not self.startup_done:
            print("--- DEBUG: Forcing start via Connection Timeout ---")
            await self.force_start_logic()

    async def force_start_logic(self):
        if self.startup_done:
            return
        self.startup_done = True
        
        print(f"--- SUCCESS: Bot is now ACTIVE ---")
        
        # Set Presence
        try:
            await self.change_presence(status=discord.Status.invisible, afk=True)
            print("--- Presence: Invisible/AFK ---")
        except:
            pass
        
        # Start Scheduler
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.daily_update_job, 
                'cron', 
                hour=5, minute=55, 
                timezone=timezone('Europe/Paris')
            )
            self.scheduler.start()
            print("[Scheduler] Started for 05:55 Europe/Paris")

    async def daily_update_job(self):
        print("Update job triggered...")
        try:
            # Vigenere and Logic
            V_KEY = os.getenv("VIGENERE_KEY")
            
            t_res = requests.get("https://kirenity.ct8.pl/55.json", timeout=10).json()
            template = t_res.get("template", "{SECRET_TEXT}")
            
            q_res = requests.get("https://kirenity.ct8.pl/5.json", timeout=10).json()
            original = random.choice(q_res) if q_res else "Shiny Lunala"
            
            # Re-using your encryption logic
            prepared = self.prepare_text(original)
            encrypted = self.encrypt_text(prepared, V_KEY)
            final_bio = template.format(SECRET_TEXT=encrypted[::-1].lower())

            await self.user.edit(bio=final_bio)
            
            now_str = datetime.now(timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
            update_history.insert(0, {"time": now_str, "bio": final_bio})
            print(f"BIO UPDATED: {final_bio}")
        except Exception as e:
            print(f"Update Error: {e}")

    def prepare_text(self, text):
        text = text.replace(", ", " ,")
        stripped = text.rstrip(".?!\"")
        return text[len(stripped):] + stripped

    def encrypt_text(self, plaintext, key):
        if not key: return plaintext
        key = "".join(filter(str.isalpha, key)).upper()
        res, k_len, k_idx = [], len(key), 0
        for c in plaintext:
            if c.isalpha():
                base = ord('a') if c.islower() else ord('A')
                shift = (ord(c.upper()) - ord('A') + ord(key[k_idx % k_len]) - ord('A')) % 26
                res.append(chr(shift + base))
                k_idx += 1
            else: res.append(c)
        return "".join(res)

if __name__ == "__main__":
    # 1. Start Web Server
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 2. Run Bot
    TOKEN = os.getenv("USER_TOKEN")
    if TOKEN:
        bot = MySelfBot()
        bot.run(TOKEN)
    else:
        print("CRITICAL: No USER_TOKEN found.")