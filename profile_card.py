"""
Profile Card Generator
Fast image generation for user profiles
"""

import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Optional
import os

class ProfileCard:
    def __init__(self):
        self.width = 900
        self.height = 450
        self.cache_dir = "profile_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Try to load fonts, fallback to default if not available
        try:
            self.font_xlarge = ImageFont.truetype("arial.ttf", 56)
            self.font_large = ImageFont.truetype("arial.ttf", 42)
            self.font_medium = ImageFont.truetype("arial.ttf", 28)
            self.font_small = ImageFont.truetype("arial.ttf", 22)
            self.font_tiny = ImageFont.truetype("arial.ttf", 16)
            self.font_bold = ImageFont.truetype("arialbd.ttf", 32)
        except:
            # Fallback to default font
            self.font_xlarge = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_tiny = ImageFont.load_default()
            self.font_bold = ImageFont.load_default()
    
    async def download_avatar(self, avatar_url: str) -> Optional[Image.Image]:
        """Download and cache user avatar"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception as e:
            print(f"Error downloading avatar: {e}")
            return None
    
    def create_gradient_background(self, color1: tuple, color2: tuple, color3: tuple = None) -> Image.Image:
        """Create smooth gradient background with optional 3-color gradient"""
        base = Image.new('RGB', (self.width, self.height), color1)
        draw = ImageDraw.Draw(base)
        
        if color3:
            # 3-color gradient
            mid_point = self.height // 2
            for i in range(mid_point):
                r = int(color1[0] + (color2[0] - color1[0]) * i / mid_point)
                g = int(color1[1] + (color2[1] - color1[1]) * i / mid_point)
                b = int(color1[2] + (color2[2] - color1[2]) * i / mid_point)
                draw.line([(0, i), (self.width, i)], fill=(r, g, b))
            for i in range(mid_point, self.height):
                r = int(color2[0] + (color3[0] - color2[0]) * (i - mid_point) / mid_point)
                g = int(color2[1] + (color3[1] - color2[1]) * (i - mid_point) / mid_point)
                b = int(color2[2] + (color3[2] - color2[2]) * (i - mid_point) / mid_point)
                draw.line([(0, i), (self.width, i)], fill=(r, g, b))
        else:
            # 2-color gradient
            for i in range(self.height):
                r = int(color1[0] + (color2[0] - color1[0]) * i / self.height)
                g = int(color1[1] + (color2[1] - color1[1]) * i / self.height)
                b = int(color1[2] + (color2[2] - color1[2]) * i / self.height)
                draw.line([(0, i), (self.width, i)], fill=(r, g, b))
        
        return base
    
    def add_rounded_corners(self, img: Image.Image, radius: int) -> Image.Image:
        """Add rounded corners to image"""
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), img.size], radius, fill=255)
        
        result = Image.new('RGBA', img.size)
        result.paste(img, (0, 0))
        result.putalpha(mask)
        return result
    
    async def generate_profile_card(
        self,
        username: str,
        avatar_url: str,
        level: int,
        xp: int,
        xp_needed: int,
        balance: int,
        bank: int,
        streak: int,
        wins: int,
        losses: int,
        is_infinity: bool = False,
        equipped_ring: str = None,
        equipped_pet: str = None,
        partner_name: str = None
    ) -> io.BytesIO:
        """Generate profile card image"""
        
        # Choose color scheme based on level (OWO-inspired)
        if is_infinity:
            color1 = (255, 223, 0)   # Bright gold
            color2 = (255, 165, 0)   # Orange
            color3 = (255, 69, 0)    # Red-orange
            accent_color = (255, 255, 255)
            badge_color = (255, 215, 0)
        elif level >= 50:
            color1 = (147, 51, 234)  # Purple
            color2 = (126, 34, 206)  # Dark purple
            color3 = (75, 0, 130)    # Indigo
            accent_color = (255, 255, 255)
            badge_color = (147, 51, 234)
        elif level >= 25:
            color1 = (59, 130, 246)  # Blue
            color2 = (37, 99, 235)   # Dark blue
            color3 = (29, 78, 216)   # Darker blue
            accent_color = (255, 255, 255)
            badge_color = (59, 130, 246)
        else:
            color1 = (34, 197, 94)   # Green
            color2 = (22, 163, 74)   # Dark green
            color3 = (21, 128, 61)   # Darker green
            accent_color = (255, 255, 255)
            badge_color = (34, 197, 94)
        
        # Create base with 3-color gradient
        img = self.create_gradient_background(color1, color2, color3)
        draw = ImageDraw.Draw(img)
        
        # Add decorative overlay pattern
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Add subtle circles pattern
        for i in range(0, self.width, 100):
            for j in range(0, self.height, 100):
                overlay_draw.ellipse(
                    [(i-20, j-20), (i+20, j+20)],
                    fill=(255, 255, 255, 10)
                )
        
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        
        # Download and add avatar with fancy border
        avatar = await self.download_avatar(avatar_url)
        if avatar:
            # Resize avatar (larger)
            avatar_size = 180
            avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            
            # Add gradient border (thicker)
            border_size = avatar_size + 16
            border = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border)
            
            # Multi-layer border effect
            for i in range(8):
                alpha = 255 - (i * 20)
                border_draw.ellipse(
                    [(i, i), (border_size-i, border_size-i)],
                    outline=(*badge_color, alpha),
                    width=2
                )
            
            # Paste avatar with border
            img_rgba = img.convert('RGBA')
            img_rgba.paste(border, (30, 30), border)
            
            output = Image.new('RGBA', avatar.size, (0, 0, 0, 0))
            output.paste(avatar, (0, 0))
            output.putalpha(mask)
            img_rgba.paste(output, (38, 38), output)
            img = img_rgba.convert('RGB')
        
        # Create new draw object for RGB image
        draw = ImageDraw.Draw(img)
        
        # Username with shadow effect
        shadow_offset = 3
        draw.text((243+shadow_offset, 43+shadow_offset), username, fill=(0, 0, 0, 128), font=self.font_xlarge)
        draw.text((243, 43), username, fill=accent_color, font=self.font_xlarge)
        
        # Level badge (rounded rectangle)
        level_badge_x = 243
        level_badge_y = 110
        if is_infinity:
            level_text = "∞"
            xp_text = "MAX LEVEL"
        else:
            level_text = str(level)
            xp_text = f"{xp:,} / {xp_needed:,} XP"
        
        # Draw level badge background
        badge_width = 120
        badge_height = 50
        draw.rounded_rectangle(
            [(level_badge_x, level_badge_y), (level_badge_x + badge_width, level_badge_y + badge_height)],
            radius=15,
            fill=(0, 0, 0, 100)
        )
        
        # Level number (centered in badge)
        level_bbox = draw.textbbox((0, 0), level_text, font=self.font_large)
        level_width = level_bbox[2] - level_bbox[0]
        level_x = level_badge_x + (badge_width - level_width) // 2
        draw.text((level_x, level_badge_y + 5), level_text, fill=badge_color, font=self.font_large)
        
        # "LEVEL" label
        draw.text((level_badge_x + 10, level_badge_y - 25), "LEVEL", fill=(255, 255, 255, 200), font=self.font_tiny)
        
        # XP text
        draw.text((243, 175), xp_text, fill=accent_color, font=self.font_small)
        
        # XP Progress bar (if not infinity) - Modern design
        if not is_infinity:
            bar_x = 243
            bar_y = 210
            bar_width = 620
            bar_height = 30
            
            # Background bar with shadow
            draw.rounded_rectangle(
                [(bar_x+2, bar_y+2), (bar_x + bar_width+2, bar_y + bar_height+2)],
                radius=15,
                fill=(0, 0, 0, 80)
            )
            draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
                radius=15,
                fill=(40, 40, 40, 255)
            )
            
            # Progress bar with gradient effect
            progress = min(xp / xp_needed, 1.0)
            progress_width = int(bar_width * progress)
            if progress_width > 0:
                # Create gradient for progress bar
                for i in range(progress_width):
                    alpha = 255
                    ratio = i / progress_width
                    r = int(badge_color[0] + (255 - badge_color[0]) * ratio * 0.3)
                    g = int(badge_color[1] + (255 - badge_color[1]) * ratio * 0.3)
                    b = int(badge_color[2] + (255 - badge_color[2]) * ratio * 0.3)
                    draw.line(
                        [(bar_x + i, bar_y), (bar_x + i, bar_y + bar_height)],
                        fill=(r, g, b, alpha)
                    )
                
                # Add shine effect
                draw.rounded_rectangle(
                    [(bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height)],
                    radius=15,
                    outline=(255, 255, 255, 100),
                    width=2
                )
            
            # Progress percentage
            progress_pct = f"{int(progress * 100)}%"
            pct_bbox = draw.textbbox((0, 0), progress_pct, font=self.font_small)
            pct_width = pct_bbox[2] - pct_bbox[0]
            draw.text(
                (bar_x + bar_width - pct_width - 10, bar_y + 3),
                progress_pct,
                fill=(255, 255, 255),
                font=self.font_small
            )
        
        # Stats section with cards
        stats_y = 270
        
        # Create stat cards
        def draw_stat_card(x, y, width, height, icon, label, value, color):
            # Card background
            draw.rounded_rectangle(
                [(x, y), (x + width, y + height)],
                radius=12,
                fill=(0, 0, 0, 120)
            )
            # Icon/Emoji
            draw.text((x + 10, y + 8), icon, fill=color, font=self.font_medium)
            # Label
            draw.text((x + 50, y + 10), label, fill=(200, 200, 200), font=self.font_tiny)
            # Value
            draw.text((x + 50, y + 30), value, fill=accent_color, font=self.font_small)
        
        # Balance card
        if is_infinity:
            balance_val = "∞"
            bank_val = "∞"
        else:
            balance_val = f"{balance:,}"
            bank_val = f"{bank:,}"
        
        draw_stat_card(40, stats_y, 200, 70, "💰", "WALLET", balance_val, (255, 215, 0))
        draw_stat_card(260, stats_y, 200, 70, "🏦", "BANK", bank_val, (100, 149, 237))
        draw_stat_card(480, stats_y, 200, 70, "🔥", "STREAK", f"{streak} days", (255, 69, 0))
        
        # Win/Loss stats card
        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        draw_stat_card(700, stats_y, 170, 70, "🎮", "WIN RATE", f"{win_rate:.1f}%", (50, 205, 50))
        
        # Win/Loss details
        draw.text((710, stats_y + 50), f"W:{wins} L:{losses}", fill=(180, 180, 180), font=self.font_tiny)
        
        # Special badges
        badge_x = 820
        badge_y = 20
        
        if is_infinity:
            # Infinity badge with glow
            draw.text((badge_x+2, badge_y+2), "♾️", fill=(0, 0, 0, 100), font=self.font_xlarge)
            draw.text((badge_x, badge_y), "♾️", fill=(255, 215, 0), font=self.font_xlarge)
            draw.text((badge_x-15, badge_y+60), "INFINITY", fill=(255, 215, 0), font=self.font_tiny)
        elif level >= 50:
            draw.text((badge_x, badge_y), "👑", fill=(255, 215, 0), font=self.font_xlarge)
            draw.text((badge_x-5, badge_y+60), "LEGEND", fill=(255, 215, 0), font=self.font_tiny)
        elif level >= 25:
            draw.text((badge_x, badge_y), "⭐", fill=(255, 255, 255), font=self.font_xlarge)
            draw.text((badge_x-10, badge_y+60), "VETERAN", fill=(255, 255, 255), font=self.font_tiny)
        
        # Equipped items section
        equip_y = 360
        if equipped_ring or equipped_pet or partner_name:
            # Draw equipped items card
            draw.rounded_rectangle(
                [(40, equip_y), (870, equip_y + 40)],
                radius=10,
                fill=(0, 0, 0, 100)
            )
            
            equip_x = 50
            if partner_name:
                draw.text((equip_x, equip_y + 10), f"💑 {partner_name}", fill=(255, 182, 193), font=self.font_small)
                equip_x += 250
            if equipped_ring:
                draw.text((equip_x, equip_y + 10), f"💍 {equipped_ring}", fill=(255, 215, 0), font=self.font_small)
                equip_x += 250
            if equipped_pet:
                draw.text((equip_x, equip_y + 10), f"🐾 {equipped_pet}", fill=(100, 200, 255), font=self.font_small)
        
        # Footer text
        draw.text((40, 420), "Doro Bot Profile Card • Use +about for item info", fill=(200, 200, 200, 150), font=self.font_tiny)
        draw.text((750, 420), "v2.1", fill=(200, 200, 200, 150), font=self.font_tiny)
        
        # Add rounded corners
        img = self.add_rounded_corners(img, 20)
        
        # Save to BytesIO
        output = io.BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        
        return output

# Global instance
profile_card_generator = ProfileCard()
