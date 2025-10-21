import os
import json
from datetime import datetime
from typing import Dict, Optional

AFK_FILE = "afk_data.json"

class AFKSystem:
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        """Load AFK data from file"""
        if os.path.exists(AFK_FILE):
            try:
                with open(AFK_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def save_data(self):
        """Save AFK data to file"""
        with open(AFK_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def set_afk(self, user_id: str, reason: Optional[str] = None):
        """Set user as AFK"""
        self.data[user_id] = {
            "reason": reason or "AFK",
            "timestamp": datetime.now().isoformat()
        }
        self.save_data()
    
    def remove_afk(self, user_id: str) -> Optional[Dict]:
        """Remove AFK status and return the data"""
        if user_id in self.data:
            data = self.data.pop(user_id)
            self.save_data()
            return data
        return None
    
    def is_afk(self, user_id: str) -> bool:
        """Check if user is AFK"""
        return user_id in self.data
    
    def get_afk(self, user_id: str) -> Optional[Dict]:
        """Get AFK data for user"""
        return self.data.get(user_id)
    
    def get_afk_duration(self, user_id: str) -> Optional[str]:
        """Get formatted AFK duration"""
        if user_id not in self.data:
            return None
        
        afk_time = datetime.fromisoformat(self.data[user_id]["timestamp"])
        duration = datetime.now() - afk_time
        
        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        
        return " ".join(parts)

# Global AFK instance
afk_system = AFKSystem()
