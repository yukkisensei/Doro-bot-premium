import os
import sys

import discord
from discord.ext import commands

from dotenv import load_dotenv

import lenh
import ai

# Load environment variables
load_dotenv()

if sys.version_info < (3, 12, 0) or sys.version_info >= (3, 13, 0):
    detected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    raise RuntimeError(
        "Discord bot requires Python 3.12.x (tested on 3.12.10). "
        f"Detected Python {detected}. Please install Python 3.12.10."
    )

if sys.version_info[:3] != (3, 12, 10):
    detected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(
        "⚠️  Bot is validated on Python 3.12.10. "
        f"Current interpreter is {detected}. Consider switching to 3.12.10 for stability"
    )

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

if not TOKEN:
    raise ValueError("Missing DISCORD_BOT_TOKEN in .env file")
if not NVIDIA_API_KEY:
    print("⚠️ Warning: Missing NVIDIA_API_KEY in .env file — AI chat will not work")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="with you 💕"))
    print(f"✅ Logged in as {bot.user}")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Error syncing slash commands: {e}")

def main():
    lenh.setup(bot)
    bot.run(TOKEN)

if __name__ == "__main__":
    main()