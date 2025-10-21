# Discord Bot - Multi-Purpose Bot

A feature-rich Discord bot with economy system, shop, marriage system, casino games, AI chat, and more!

## ✨ Features

### 💰 Economy System
- Wallet & Bank system
- Daily rewards (500-1500 coins/24h)
- Money transfer between users
- Stats tracking (wins/losses, total earned/spent)
- Leaderboard (top 10 richest users)

### 🏪 Shop & Inventory
- **Shop Categories:**
  - 💍 Rings (1M-10M coins) - Marriage items
  - 🐾 Pets - XP boost items
  - 🎁 Lootboxes - Random rewards
  - 🍪 Consumables - Casino buffs
  - 💎 Collectibles - Rare items
- **Features:**
  - Buy, sell (50% price), gift items
  - Equip/unequip system
  - Inventory management
  - Item effects and buffs

### 💍 Marriage System
- Propose with rings
- Accept/reject proposals (5 min timeout)
- Marriage info (partner, ring, duration, love points)
- Divorce system
- **Note:** Ring buffs only work when married!

### 🎰 Casino Games
- **Coinflip** - Heads/Tails betting (x2 payout)
- **Slots** - 6 symbols with x2-x10 multipliers
- **Blackjack** - Classic card game vs dealer
- **Tài Xỉu** - Vietnamese dice game (3 dice)

### 🤖 AI Chat
- Powered by NVIDIA API (Llama 3.1)
- 20 message history per user
- Memory system (save/recall/forget)
- Model switching support
- Personality system

### 🎮 Fun & Interaction
- **Fun Commands:** 8ball, dice, coinflip, RPS
- **Interaction Commands:** hug, kiss, pat, slap, cuddle, poke, tickle, highfive, boop, wave, nom, stare

### 🛠️ Utility
- Profile card generator with equipped items
- AFK system with auto-detection
- Command disable system (channel-specific)
- Server/user info commands

## 📋 Requirements

- Python 3.12.10
- Discord Bot Token
- NVIDIA API Key (for AI chat)

## 🚀 Installation

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd <repo-folder>
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
Copy `.env.example` to `.env` and fill in your credentials:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
NVIDIA_API_KEY=your_nvidia_api_key_here
BOT_OWNER_IDS=your_discord_user_id_here
```

### 4. Run the bot
```bash
python main.py
```

## 📖 Commands

### Economy Commands
- `+balance [@user]` - Check balance
- `+daily` - Claim daily reward
- `+deposit <amount>` - Deposit to bank
- `+withdraw <amount>` - Withdraw from bank
- `+give @user <amount>` - Give money
- `+stats [@user]` - View stats
- `+leaderboard` - Top 10 richest

### Shop Commands
- `+shop [category]` - View shop
- `+buy <item_id> [quantity]` - Buy item
- `+inventory [@user]` - View inventory
- `+equip <item_id>` - Equip item
- `+unequip <ring/pet>` - Unequip item
- `+use <item_id>` - Use item
- `+sell <item_id> [quantity]` - Sell item (50% price)
- `+gift @user <item_id>` - Gift item
- `+about [category]` - View item details

### Marriage Commands
- `+marry @user` - Propose (requires equipped ring)
- `+accept` - Accept proposal
- `+reject` - Reject proposal
- `+divorce` - Divorce
- `+marriage [@user]` - View marriage info

### Casino Commands
- `+cf <heads/tails> <amount>` - Coinflip
- `+slots <amount>` - Slots machine
- `+bj <amount>` - Blackjack
- `+gamble <tai/xiu> <amount>` - Tài Xỉu

### AI Commands
- `@bot <message>` - Chat with AI
- `+reset` - Reset chat history
- `+remember <key> <value>` - Save memory
- `+recall <key>` - Recall memory
- `+forget <key>` - Forget memory

### Fun Commands
- `+8ball <question>` - Magic 8ball
- `+dice [NdN]` - Roll dice
- `+coinflip` - Flip a coin
- `+rps <rock/paper/scissors>` - Rock Paper Scissors

### Interaction Commands
- `+hug @user` - Hug someone
- `+kiss @user` - Kiss someone
- `+pat @user` - Pat someone
- `+slap @user` - Slap someone
- `+cuddle @user` - Cuddle someone
- `+poke @user` - Poke someone
- `+tickle @user` - Tickle someone
- `+highfive @user` - High five
- `+boop @user` - Boop nose
- `+wave @user` - Wave hand
- `+nom @user` - Nom nom
- `+stare @user` - Stare at someone

### Utility Commands
- `+help` - Show all commands
- `+about [category]` - Item information
- `+avatar [@user]` - View avatar
- `+serverinfo` - Server information
- `+userinfo [@user]` - User information
- `+card [@user]` - Generate profile card
- `+afk [reason]` - Set AFK status

### Slash Commands (Owner Only)
- `/disable` - Disable commands in channel
- `/enable` - Enable commands in channel
- `/disabled` - View disabled commands
- `/clearall` - Clear all disabled commands

## 🎨 Shop Items

### 💍 Rings (Marriage Items)
**⚠️ Ring buffs only work when married!**
- 💍 Nhẫn Tình Yêu - 1,000,000 coins (+5% daily coins)
- 💕 Nhẫn Cặp Đôi Tình Ái - 2,500,000 coins (+10% daily coins)
- 🦆 Nhẫn Uyên Ương - 5,000,000 coins (+15% daily coins)
- 💎 Nhẫn Vĩnh Cửu - 7,500,000 coins (+25% daily coins)
- ✨ Nhẫn Định Mệnh - 10,000,000 coins (+50% daily coins)

### 🐾 Pets (XP Boost)
- 🐶 Chó Shiba - 50,000 coins (+5% XP)
- 🐱 Mèo Munchkin - 100,000 coins (+10% XP)
- 🦊 Cáo Fennec - 250,000 coins (+15% XP)
- 🐼 Gấu Trúc - 500,000 coins (+20% XP)
- 🦄 Kỳ Lân - 1,000,000 coins (+25% XP)

### 🎁 Lootboxes
- 📦 Common Box - 5,000 coins
- 🎁 Rare Box - 15,000 coins
- 💎 Epic Box - 50,000 coins
- ✨ Legendary Box - 150,000 coins

### 🍪 Consumables (Casino Buffs)
- 🍪 Lucky Cookie - 10,000 coins (+10% win rate, 3 games)
- 🍀 Four Leaf Clover - 25,000 coins (+20% win rate, 5 games)
- 🌟 Star Fragment - 50,000 coins (+30% win rate, 10 games)

### 💎 Collectibles
- 🏆 Trophy - 100,000 coins
- 👑 Crown - 500,000 coins
- 💠 Crystal - 1,000,000 coins

## 📊 Data Storage

All data is stored in JSON files:
- `economy_data.json` - User balances, stats
- `user_inventory.json` - Shop items, equipped items
- `marriage_data.json` - Marriage records
- `afk_data.json` - AFK statuses
- `disabled_commands.json` - Disabled commands
- `user_histories/` - AI chat histories

## 🔧 Configuration

### Bot Prefix
Default: `+` (can be changed in `main.py`)

### Owner IDs
Set in `.env` file:
```env
BOT_OWNER_IDS=123456789,987654321
```

### AI Model
Default: `meta/llama-3.1-8b-instruct`
Can be changed with `+model` command (owner only)

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📝 License

This project is licensed under the MIT License.

## ⚠️ Disclaimer

This bot is provided as-is. Make sure to:
- Keep your `.env` file secure
- Don't share your bot token or API keys
- Backup your data files regularly

## 🆘 Support

If you encounter any issues:
1. Check the `.env` file configuration
2. Verify Python version (3.12.10)
3. Make sure all dependencies are installed
4. Check bot permissions in Discord

## 🎉 Credits

Built with:
- [discord.py](https://github.com/Rapptz/discord.py)
- [NVIDIA API](https://build.nvidia.com/)
- [Pillow](https://python-pillow.org/)
- [aiohttp](https://docs.aiohttp.org/)

---

**Enjoy using the bot! 🎮💕**
