"""
Shop System - OWO-style shop with items
Includes rings, boxes, and special items
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class ShopSystem:
    """Manage shop items and user inventory"""
    
    def __init__(self):
        self.data_file = "shop_data.json"
        self.inventory_file = "user_inventory.json"
        
        # Shop items with Vietnamese names
        self.shop_items = {
            # ===== RINGS (Nhẫn) =====
            "ring_love": {
                "name": "💍 Nhẫn Tình Yêu",
                "description": "Chiếc nhẫn tượng trưng cho tình yêu chân thành",
                "price": 1000000,
                "category": "ring",
                "emoji": "💍",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 5% coins khi dùng +daily"
            },
            "ring_couple": {
                "name": "💕 Nhẫn Cặp Đôi Tình Ái",
                "description": "Nhẫn dành cho những cặp đôi yêu nhau",
                "price": 2500000,
                "category": "ring",
                "emoji": "💕",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 10% coins khi dùng +daily"
            },
            "ring_mandarin": {
                "name": "🦆 Nhẫn Uyên Ương",
                "description": "Nhẫn của đôi chim uyên ương bất ly bất khác",
                "price": 5000000,
                "category": "ring",
                "emoji": "🦆",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 15% coins khi dùng +daily"
            },
            "ring_eternal": {
                "name": "💎 Nhẫn Vĩnh Cửu",
                "description": "Nhẫn kim cương tượng trưng cho tình yêu vĩnh cửu",
                "price": 7500000,
                "category": "ring",
                "emoji": "💎",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 25% coins khi dùng +daily"
            },
            "ring_destiny": {
                "name": "✨ Nhẫn Định Mệnh",
                "description": "Nhẫn của những người được định mệnh gắn kết",
                "price": 10000000,
                "category": "ring",
                "emoji": "✨",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 50% coins khi dùng +daily"
            },
            
            # ===== LOOTBOXES (Hộp Quà) =====
            "box_common": {
                "name": "📦 Hộp Quà Thường",
                "description": "Hộp quà cơ bản chứa vật phẩm ngẫu nhiên",
                "price": 1000,
                "category": "lootbox",
                "emoji": "📦",
                "tradeable": True,
                "usable": True,
                "effect": "Mở để nhận vật phẩm ngẫu nhiên"
            },
            "box_rare": {
                "name": "🎁 Hộp Quà Hiếm",
                "description": "Hộp quà hiếm chứa vật phẩm giá trị",
                "price": 5000,
                "category": "lootbox",
                "emoji": "🎁",
                "tradeable": True,
                "usable": True,
                "effect": "Mở để nhận vật phẩm hiếm"
            },
            "box_epic": {
                "name": "🎀 Hộp Quà Sử Thi",
                "description": "Hộp quà sử thi với phần thưởng lớn",
                "price": 15000,
                "category": "lootbox",
                "emoji": "🎀",
                "tradeable": True,
                "usable": True,
                "effect": "Mở để nhận vật phẩm sử thi"
            },
            "box_legendary": {
                "name": "🎊 Hộp Quà Huyền Thoại",
                "description": "Hộp quà huyền thoại với kho báu vô giá",
                "price": 50000,
                "category": "lootbox",
                "emoji": "🎊",
                "tradeable": True,
                "usable": True,
                "effect": "Mở để nhận vật phẩm huyền thoại"
            },
            
            # ===== SPECIAL ITEMS (Vật Phẩm Đặc Biệt) =====
            "cookie": {
                "name": "🍪 Bánh Quy May Mắn",
                "description": "Bánh quy mang lại may mắn trong casino",
                "price": 2000,
                "category": "consumable",
                "emoji": "🍪",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 10% tỷ lệ thắng casino (1 lần)"
            },
            "clover": {
                "name": "🍀 Cỏ Bốn Lá",
                "description": "Cỏ bốn lá hiếm mang lại vận may",
                "price": 5000,
                "category": "consumable",
                "emoji": "🍀",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 20% tỷ lệ thắng casino (1 lần)"
            },
            "horseshoe": {
                "name": "🧲 Móng Ngựa May Mắn",
                "description": "Móng ngựa cổ xưa mang lại tài lộc",
                "price": 10000,
                "category": "consumable",
                "emoji": "🧲",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 30% tỷ lệ thắng casino (1 lần)"
            },
            "gem": {
                "name": "💠 Viên Ngọc Quý",
                "description": "Viên ngọc quý hiếm có giá trị cao",
                "price": 25000,
                "category": "collectible",
                "emoji": "💠",
                "tradeable": True,
                "usable": False,
                "effect": "Vật phẩm sưu tầm"
            },
            "trophy": {
                "name": "🏆 Cúp Vàng",
                "description": "Cúp vàng dành cho người chiến thắng",
                "price": 50000,
                "category": "collectible",
                "emoji": "🏆",
                "tradeable": True,
                "usable": False,
                "effect": "Vật phẩm sưu tầm"
            },
            "crown": {
                "name": "👑 Vương Miện",
                "description": "Vương miện của bậc vua chúa",
                "price": 100000,
                "category": "collectible",
                "emoji": "👑",
                "tradeable": True,
                "usable": False,
                "effect": "Vật phẩm sưu tầm"
            },
            
            # ===== PETS (Thú Cưng) =====
            "pet_cat": {
                "name": "🐱 Mèo Cưng",
                "description": "Chú mèo đáng yêu và trung thành",
                "price": 15000,
                "category": "pet",
                "emoji": "🐱",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 5% XP mỗi ngày"
            },
            "pet_dog": {
                "name": "🐶 Chó Cưng",
                "description": "Chú chó thông minh và dũng cảm",
                "price": 15000,
                "category": "pet",
                "emoji": "🐶",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 5% XP mỗi ngày"
            },
            "pet_dragon": {
                "name": "🐉 Rồng Thần",
                "description": "Rồng thần huyền thoại mang lại sức mạnh",
                "price": 75000,
                "category": "pet",
                "emoji": "🐉",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 15% XP mỗi ngày"
            },
            "pet_phoenix": {
                "name": "🦅 Phượng Hoàng",
                "description": "Phượng hoàng bất tử với sức mạnh tái sinh",
                "price": 150000,
                "category": "pet",
                "emoji": "🦅",
                "tradeable": True,
                "usable": True,
                "effect": "Tăng 25% XP mỗi ngày"
            },
        }
        
        self.load_data()
    
    def load_data(self):
        """Load user inventory data"""
        if os.path.exists(self.inventory_file):
            try:
                with open(self.inventory_file, 'r', encoding='utf-8') as f:
                    self.inventory_data = json.load(f)
            except:
                self.inventory_data = {}
        else:
            self.inventory_data = {}
    
    def save_data(self):
        """Save user inventory data"""
        with open(self.inventory_file, 'w', encoding='utf-8') as f:
            json.dump(self.inventory_data, f, ensure_ascii=False, indent=2)
    
    def get_user_inventory(self, user_id: str) -> Dict:
        """Get user's inventory"""
        if user_id not in self.inventory_data:
            self.inventory_data[user_id] = {
                "items": {},
                "equipped": {},
                "active_effects": []
            }
            self.save_data()
        return self.inventory_data[user_id]
    
    def add_item(self, user_id: str, item_id: str, quantity: int = 1) -> bool:
        """Add item to user's inventory"""
        inventory = self.get_user_inventory(user_id)
        
        if item_id not in inventory["items"]:
            inventory["items"][item_id] = 0
        
        inventory["items"][item_id] += quantity
        self.save_data()
        return True
    
    def remove_item(self, user_id: str, item_id: str, quantity: int = 1) -> bool:
        """Remove item from user's inventory"""
        inventory = self.get_user_inventory(user_id)
        
        if item_id not in inventory["items"] or inventory["items"][item_id] < quantity:
            return False
        
        inventory["items"][item_id] -= quantity
        if inventory["items"][item_id] <= 0:
            del inventory["items"][item_id]
        
        self.save_data()
        return True
    
    def has_item(self, user_id: str, item_id: str, quantity: int = 1) -> bool:
        """Check if user has item"""
        inventory = self.get_user_inventory(user_id)
        return inventory["items"].get(item_id, 0) >= quantity
    
    def get_item_count(self, user_id: str, item_id: str) -> int:
        """Get item count"""
        inventory = self.get_user_inventory(user_id)
        return inventory["items"].get(item_id, 0)
    
    def get_shop_items(self, category: str = None) -> Dict:
        """Get shop items, optionally filtered by category"""
        if category:
            return {k: v for k, v in self.shop_items.items() if v["category"] == category}
        return self.shop_items
    
    def get_item_info(self, item_id: str) -> Optional[Dict]:
        """Get item information"""
        return self.shop_items.get(item_id)
    
    def equip_item(self, user_id: str, item_id: str) -> Tuple[bool, str]:
        """Equip an item (rings, pets)"""
        inventory = self.get_user_inventory(user_id)
        
        if not self.has_item(user_id, item_id):
            return False, "Bạn không có vật phẩm này!"
        
        item = self.get_item_info(item_id)
        if not item:
            return False, "Vật phẩm không tồn tại!"
        
        category = item["category"]
        
        # Check if category can be equipped
        if category not in ["ring", "pet"]:
            return False, "Vật phẩm này không thể trang bị!"
        
        # Unequip old item if exists
        if category in inventory["equipped"]:
            old_item = inventory["equipped"][category]
            if old_item != item_id:
                # Add old item back to inventory
                self.add_item(user_id, old_item, 1)
        
        # Equip new item
        inventory["equipped"][category] = item_id
        self.remove_item(user_id, item_id, 1)
        self.save_data()
        
        return True, f"Đã trang bị {item['emoji']} {item['name']}!"
    
    def unequip_item(self, user_id: str, category: str) -> Tuple[bool, str]:
        """Unequip an item"""
        inventory = self.get_user_inventory(user_id)
        
        if category not in inventory["equipped"]:
            return False, f"Bạn chưa trang bị {category} nào!"
        
        item_id = inventory["equipped"][category]
        item = self.get_item_info(item_id)
        
        # Add item back to inventory
        self.add_item(user_id, item_id, 1)
        del inventory["equipped"][category]
        self.save_data()
        
        return True, f"Đã gỡ {item['emoji']} {item['name']}!"
    
    def get_equipped_item(self, user_id: str, category: str) -> Optional[str]:
        """Get equipped item ID for category"""
        inventory = self.get_user_inventory(user_id)
        return inventory["equipped"].get(category)
    
    def use_item(self, user_id: str, item_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """Use a consumable item"""
        if not self.has_item(user_id, item_id):
            return False, "Bạn không có vật phẩm này!", None
        
        item = self.get_item_info(item_id)
        if not item or not item.get("usable"):
            return False, "Vật phẩm này không thể sử dụng!", None
        
        # Remove item
        self.remove_item(user_id, item_id, 1)
        
        # Return effect data
        effect_data = {
            "type": item["category"],
            "effect": item["effect"],
            "item_name": item["name"]
        }
        
        return True, f"Đã sử dụng {item['emoji']} {item['name']}!", effect_data
    
    def open_lootbox(self, user_id: str, box_id: str) -> Tuple[bool, str, List[Dict]]:
        """Open a lootbox and get rewards"""
        if not self.has_item(user_id, box_id):
            return False, "Bạn không có hộp quà này!", []
        
        item = self.get_item_info(box_id)
        if not item or item["category"] != "lootbox":
            return False, "Đây không phải hộp quà!", []
        
        # Remove lootbox
        self.remove_item(user_id, box_id, 1)
        
        # Generate rewards based on box rarity
        import random
        rewards = []
        
        if box_id == "box_common":
            # Common box: 1-3 items, mostly common
            num_items = random.randint(1, 3)
            possible_items = ["cookie", "pet_cat", "pet_dog", "gem"]
            coins = random.randint(500, 2000)
        elif box_id == "box_rare":
            # Rare box: 2-4 items, mix of common and rare
            num_items = random.randint(2, 4)
            possible_items = ["cookie", "clover", "ring_love", "ring_couple", "gem", "trophy"]
            coins = random.randint(2000, 5000)
        elif box_id == "box_epic":
            # Epic box: 3-5 items, mostly rare and epic
            num_items = random.randint(3, 5)
            possible_items = ["clover", "horseshoe", "ring_couple", "ring_mandarin", "ring_eternal", "trophy", "pet_dragon"]
            coins = random.randint(5000, 15000)
        else:  # legendary
            # Legendary box: 4-6 items, epic and legendary
            num_items = random.randint(4, 6)
            possible_items = ["horseshoe", "ring_eternal", "ring_destiny", "trophy", "crown", "pet_dragon", "pet_phoenix"]
            coins = random.randint(15000, 50000)
        
        # Add coins reward
        rewards.append({
            "type": "coins",
            "amount": coins,
            "emoji": "💰",
            "name": f"{coins:,} coins"
        })
        
        # Add random items
        for _ in range(num_items):
            item_id = random.choice(possible_items)
            self.add_item(user_id, item_id, 1)
            item_info = self.get_item_info(item_id)
            rewards.append({
                "type": "item",
                "item_id": item_id,
                "emoji": item_info["emoji"],
                "name": item_info["name"]
            })
        
        return True, f"Đã mở {item['emoji']} {item['name']}!", rewards
    
    def get_inventory_value(self, user_id: str) -> int:
        """Calculate total inventory value"""
        inventory = self.get_user_inventory(user_id)
        total = 0
        
        for item_id, quantity in inventory["items"].items():
            item = self.get_item_info(item_id)
            if item:
                total += item["price"] * quantity
        
        for item_id in inventory["equipped"].values():
            item = self.get_item_info(item_id)
            if item:
                total += item["price"]
        
        return total

# Global instance
shop_system = ShopSystem()
