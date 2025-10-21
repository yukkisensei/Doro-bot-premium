import os
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Optional

# File lưu trữ economy data
ECONOMY_FILE = "economy_data.json"

class EconomySystem:
    def __init__(self):
        self.data = self.load_data()
        self.owner_ids = []  # Will be set from lenh.py
    
    def load_data(self) -> Dict:
        """Load economy data from file"""
        if os.path.exists(ECONOMY_FILE):
            try:
                with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def save_data(self):
        """Save economy data to file"""
        with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id: str) -> Dict:
        """Get user data, create if not exists"""
        if user_id not in self.data:
            self.data[user_id] = {
                "balance": 1000,  # Starting balance
                "bank": 0,
                "last_daily": None,
                "daily_streak": 0,  # Consecutive days
                "base_daily": random.randint(100, 400),  # Base daily amount (100-400)
                "xp": 0,
                "level": 1,
                "infinity": False,  # Owner can have infinite coins/level
                "total_earned": 1000,
                "total_spent": 0,
                "wins": 0,
                "losses": 0,
                "created_at": datetime.now().isoformat()
            }
            self.save_data()
        
        # Migrate old data - add missing fields
        user = self.data[user_id]
        updated = False
        
        if "level" not in user:
            user["level"] = 1
            updated = True
        
        if "xp" not in user:
            user["xp"] = 0
            updated = True
        
        if "daily_streak" not in user:
            user["daily_streak"] = 0
            updated = True
        
        if "base_daily" not in user:
            user["base_daily"] = random.randint(100, 400)
            updated = True
        
        if "infinity" not in user:
            user["infinity"] = False
            updated = True
        
        if updated:
            self.save_data()
        
        return user
    
    def is_infinity(self, user_id: str) -> bool:
        """Check if user has infinity mode"""
        user = self.get_user(user_id)
        return user.get("infinity", False)
    
    def set_infinity(self, user_id: str, enabled: bool = True):
        """Set infinity mode for user (owner only)"""
        user = self.get_user(user_id)
        user["infinity"] = enabled
        self.save_data()
    
    def get_balance(self, user_id: str) -> int:
        """Get user's wallet balance"""
        if self.is_infinity(user_id):
            return float('inf')
        return self.get_user(user_id)["balance"]
    
    def get_bank(self, user_id: str) -> int:
        """Get user's bank balance"""
        if self.is_infinity(user_id):
            return float('inf')
        return self.get_user(user_id)["bank"]
    
    def add_money(self, user_id: str, amount: int, to_bank: bool = False):
        """Add money to user's wallet or bank"""
        user = self.get_user(user_id)
        if to_bank:
            user["bank"] += amount
        else:
            user["balance"] += amount
        user["total_earned"] += amount
        self.save_data()
    
    def remove_money(self, user_id: str, amount: int, from_bank: bool = False) -> bool:
        """Remove money from user's wallet or bank"""
        # Infinity users never lose money
        if self.is_infinity(user_id):
            return True
        
        user = self.get_user(user_id)
        if from_bank:
            if user["bank"] >= amount:
                user["bank"] -= amount
                user["total_spent"] += amount
                self.save_data()
                return True
        else:
            if user["balance"] >= amount:
                user["balance"] -= amount
                user["total_spent"] += amount
                self.save_data()
                return True
        return False
    
    def transfer(self, from_user: str, to_user: str, amount: int) -> bool:
        """Transfer money between users"""
        # Infinity users can give unlimited money
        if self.is_infinity(from_user):
            self.add_money(to_user, amount)
            return True
        
        if self.remove_money(from_user, amount):
            self.add_money(to_user, amount)
            return True
        return False
    
    def can_daily(self, user_id: str) -> bool:
        """Check if user can claim daily reward"""
        user = self.get_user(user_id)
        if user["last_daily"] is None:
            return True
        last_daily = datetime.fromisoformat(user["last_daily"])
        return datetime.now() - last_daily >= timedelta(hours=24)
    
    def set_level(self, user_id: str, level: int):
        """Set user level (owner only)"""
        user = self.get_user(user_id)
        user["level"] = level
        user["xp"] = 0  # Reset XP when setting level
        self.save_data()
    
    def get_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a level"""
        return int(100 * (level ** 1.5))
    
    def add_xp(self, user_id: str, amount: int) -> Optional[int]:
        """Add XP to user, return new level if leveled up"""
        user = self.get_user(user_id)
        user["xp"] = user.get("xp", 0) + amount
        
        current_level = user.get("level", 1)
        xp_needed = self.get_xp_for_level(current_level)
        
        if user["xp"] >= xp_needed:
            user["xp"] -= xp_needed
            user["level"] = current_level + 1
            self.save_data()
            return user["level"]
        
        self.save_data()
        return None
    
    def claim_daily(self, user_id: str) -> Dict:
        """Claim daily reward with streak bonus"""
        user = self.get_user(user_id)
        
        # Check if streak continues (within 48h)
        if user["last_daily"]:
            last_daily = datetime.fromisoformat(user["last_daily"])
            hours_since = (datetime.now() - last_daily).total_seconds() / 3600
            
            if hours_since < 48:  # Within 48h = streak continues
                user["daily_streak"] = user.get("daily_streak", 0) + 1
            else:  # Streak broken
                user["daily_streak"] = 1
        else:
            user["daily_streak"] = 1
        
        # Get base daily amount (unique per user, max 300 coin difference)
        if "base_daily" not in user:
            user["base_daily"] = random.randint(100, 400)
        
        base_amount = user["base_daily"]
        streak = user["daily_streak"]
        level = user.get("level", 1)
        
        # Calculate bonus
        # Base: 1% per day streak
        # Level bonus: +0.4% per level
        streak_bonus = 1 + (streak * 0.01)  # 1% per day
        level_bonus = 1 + (level * 0.004)   # 0.4% per level
        
        total_multiplier = streak_bonus * level_bonus
        amount = int(base_amount * total_multiplier)
        
        # Add money and XP
        user["balance"] += amount
        user["total_earned"] += amount
        user["last_daily"] = datetime.now().isoformat()
        
        # Award XP (10 XP per daily)
        xp_gained = 10
        user["xp"] = user.get("xp", 0) + xp_gained
        
        # Check level up
        new_level = None
        current_level = user.get("level", 1)
        xp_needed = self.get_xp_for_level(current_level)
        
        if user["xp"] >= xp_needed:
            user["xp"] -= xp_needed
            user["level"] = current_level + 1
            new_level = user["level"]
        
        self.save_data()
        
        return {
            "amount": amount,
            "streak": streak,
            "level": user["level"],
            "xp_gained": xp_gained,
            "new_level": new_level,
            "streak_bonus": (streak_bonus - 1) * 100,  # as percentage
            "level_bonus": (level_bonus - 1) * 100     # as percentage
        }
    
    def record_win(self, user_id: str):
        """Record a win"""
        user = self.get_user(user_id)
        user["wins"] += 1
        self.save_data()
    
    def record_loss(self, user_id: str):
        """Record a loss"""
        user = self.get_user(user_id)
        user["losses"] += 1
        self.save_data()
    
    def get_stats(self, user_id: str) -> Dict:
        """Get user statistics"""
        return self.get_user(user_id)
    
    def deposit(self, user_id: str, amount: int) -> bool:
        """Deposit money to bank"""
        # Infinity users don't need to deposit
        if self.is_infinity(user_id):
            return True
        
        user = self.get_user(user_id)
        if user["balance"] >= amount:
            user["balance"] -= amount
            user["bank"] += amount
            self.save_data()
            return True
        return False
    
    def withdraw(self, user_id: str, amount: int) -> bool:
        """Withdraw money from bank"""
        # Infinity users don't need to withdraw
        if self.is_infinity(user_id):
            return True
        
        user = self.get_user(user_id)
        if user["bank"] >= amount:
            user["bank"] -= amount
            user["balance"] += amount
            self.save_data()
            return True
        return False

# Global economy instance
economy = EconomySystem()
