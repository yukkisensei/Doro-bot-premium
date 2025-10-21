import os
import json
from typing import Dict, List, Set

DISABLE_FILE = "disabled_commands.json"

class CommandDisableSystem:
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        """Load disabled commands data from file"""
        if os.path.exists(DISABLE_FILE):
            try:
                with open(DISABLE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def save_data(self):
        """Save disabled commands data to file"""
        with open(DISABLE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def disable_command(self, channel_id: str, command: str):
        """Disable a command in a specific channel"""
        if channel_id not in self.data:
            self.data[channel_id] = []
        
        if command not in self.data[channel_id]:
            self.data[channel_id].append(command)
            self.save_data()
            return True
        return False
    
    def enable_command(self, channel_id: str, command: str):
        """Enable a command in a specific channel"""
        if channel_id in self.data and command in self.data[channel_id]:
            self.data[channel_id].remove(command)
            if not self.data[channel_id]:
                del self.data[channel_id]
            self.save_data()
            return True
        return False
    
    def is_disabled(self, channel_id: str, command: str) -> bool:
        """Check if a command is disabled in a channel"""
        return channel_id in self.data and command in self.data[channel_id]
    
    def get_disabled_commands(self, channel_id: str) -> List[str]:
        """Get all disabled commands in a channel"""
        return self.data.get(channel_id, [])
    
    def clear_channel(self, channel_id: str):
        """Clear all disabled commands in a channel"""
        if channel_id in self.data:
            del self.data[channel_id]
            self.save_data()
            return True
        return False
    
    def get_all_commands(self) -> Set[str]:
        """Get list of all available commands (for autocomplete)"""
        return {
            # Music commands
            "play", "skip", "pause", "resume", "stop", "queue", "np", 
            "loop", "shuffle", "volume", "history", "move", "remove", "stay", "leave",
            
            # Economy commands
            "balance", "daily", "deposit", "withdraw", "give", "stats", "leaderboard",
            
            # Casino commands
            "cf", "slots", "bj", "gamble",
            
            # AI commands
            "reset", "remember", "recall", "forget",
            
            # Fun commands
            "8ball", "roll", "coinflip", "rps",
            
            # Utility commands
            "help", "ping", "avatar", "serverinfo", "userinfo", "say",
            
            # AFK
            "afk"
        }

# Global disable system instance
disable_system = CommandDisableSystem()
