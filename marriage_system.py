"""
Marriage System - Hệ thống cưới cho Discord bot
Cho phép users cưới nhau và nhận benefits
"""

import json
import os
from datetime import datetime
from typing import Optional, Tuple, Dict

class MarriageSystem:
    """Manage marriages between users"""
    
    def __init__(self):
        self.data_file = "marriage_data.json"
        self.load_data()
    
    def load_data(self):
        """Load marriage data"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.marriages = json.load(f)
            except:
                self.marriages = {}
        else:
            self.marriages = {}
    
    def save_data(self):
        """Save marriage data"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.marriages, f, ensure_ascii=False, indent=2)
    
    def is_married(self, user_id: str) -> bool:
        """Check if user is married"""
        return user_id in self.marriages
    
    def get_partner(self, user_id: str) -> Optional[str]:
        """Get user's partner ID"""
        if user_id in self.marriages:
            return self.marriages[user_id]["partner"]
        return None
    
    def get_marriage_info(self, user_id: str) -> Optional[Dict]:
        """Get marriage information"""
        if user_id in self.marriages:
            return self.marriages[user_id]
        return None
    
    def propose(self, proposer_id: str, target_id: str) -> Tuple[bool, str]:
        """Propose marriage to someone"""
        # Check if proposer is already married
        if self.is_married(proposer_id):
            return False, "Bạn đã kết hôn rồi! 💍"
        
        # Check if target is already married
        if self.is_married(target_id):
            return False, "Người này đã kết hôn rồi! 💔"
        
        # Check if proposing to self
        if proposer_id == target_id:
            return False, "Bạn không thể cưới chính mình! 😅"
        
        return True, "Proposal sent! ✨"
    
    def marry(self, user1_id: str, user2_id: str, ring_id: str = None) -> Tuple[bool, str]:
        """Marry two users"""
        # Validate both users are not married
        if self.is_married(user1_id) or self.is_married(user2_id):
            return False, "Một trong hai người đã kết hôn rồi!"
        
        # Create marriage record
        marriage_date = datetime.now().isoformat()
        
        self.marriages[user1_id] = {
            "partner": user2_id,
            "married_at": marriage_date,
            "ring": ring_id,
            "love_points": 0
        }
        
        self.marriages[user2_id] = {
            "partner": user1_id,
            "married_at": marriage_date,
            "ring": ring_id,
            "love_points": 0
        }
        
        self.save_data()
        return True, f"🎉 Chúc mừng! Hai bạn đã kết hôn! 💍✨"
    
    def divorce(self, user_id: str) -> Tuple[bool, str]:
        """Divorce (break marriage)"""
        if not self.is_married(user_id):
            return False, "Bạn chưa kết hôn!"
        
        partner_id = self.get_partner(user_id)
        
        # Remove both marriage records
        del self.marriages[user_id]
        if partner_id and partner_id in self.marriages:
            del self.marriages[partner_id]
        
        self.save_data()
        return True, "💔 Hai bạn đã ly hôn..."
    
    def add_love_points(self, user_id: str, points: int) -> bool:
        """Add love points to marriage"""
        if not self.is_married(user_id):
            return False
        
        self.marriages[user_id]["love_points"] += points
        
        # Also update partner's points
        partner_id = self.get_partner(user_id)
        if partner_id and partner_id in self.marriages:
            self.marriages[partner_id]["love_points"] += points
        
        self.save_data()
        return True
    
    def get_marriage_duration(self, user_id: str) -> Optional[str]:
        """Get how long user has been married"""
        if not self.is_married(user_id):
            return None
        
        married_at = datetime.fromisoformat(self.marriages[user_id]["married_at"])
        duration = datetime.now() - married_at
        
        days = duration.days
        if days == 0:
            hours = duration.seconds // 3600
            return f"{hours} giờ"
        elif days < 30:
            return f"{days} ngày"
        elif days < 365:
            months = days // 30
            return f"{months} tháng"
        else:
            years = days // 365
            return f"{years} năm"
    
    def get_all_marriages(self) -> Dict:
        """Get all marriages"""
        return self.marriages

# Global instance
marriage_system = MarriageSystem()
