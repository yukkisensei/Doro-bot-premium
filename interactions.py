"""
Interaction Commands System
OWO-style interaction commands with GIF responses
"""

import random
from typing import Dict, List

class InteractionCommands:
    """Manage interaction commands with GIF responses"""
    
    def __init__(self):
        # GIF URLs for each interaction type (using Tenor API format)
        self.interactions: Dict[str, Dict[str, any]] = {
            "kiss": {
                "gifs": [
                    "https://media.giphy.com/media/G3va31oEEnIkM/giphy.gif",
                    "https://media.giphy.com/media/bGm9FuBCGg4SY/giphy.gif",
                    "https://media.giphy.com/media/KH1CTZtw1p9ba/giphy.gif",
                    "https://media.giphy.com/media/FqBTvSNmc1mNG/giphy.gif",
                    "https://media.giphy.com/media/zkppEMFvRX5FC/giphy.gif",
                ],
                "messages": [
                    "{author} đã hôn {target}! 💋",
                    "{author} đã kiss {target}! 😘",
                    "{author} vừa hôn {target} một cái! 💕",
                    "{author} đã trao {target} một nụ hôn! ❤️",
                ]
            },
            "hug": {
                "gifs": [
                    "https://media.giphy.com/media/PHZ7v9tfQu0o0/giphy.gif",
                    "https://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif",
                    "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
                    "https://media.giphy.com/media/wnsgren9NtITS/giphy.gif",
                    "https://media.giphy.com/media/svXXBgduBsJ20/giphy.gif",
                ],
                "messages": [
                    "{author} đã ôm {target}! 🤗",
                    "{author} đang ôm {target} thật chặt! 💕",
                    "{author} vừa cho {target} một cái ôm! 🫂",
                    "{author} đã ôm {target} ấm áp! ❤️",
                ]
            },
            "pat": {
                "gifs": [
                    "https://media.giphy.com/media/ARSp9T7wwxNcs/giphy.gif",
                    "https://media.giphy.com/media/5tmRHwTlHAA9WkVxTU/giphy.gif",
                    "https://media.giphy.com/media/uw0KpagtwEJtC/giphy.gif",
                    "https://media.giphy.com/media/109ltuoSQT212w/giphy.gif",
                    "https://media.giphy.com/media/L2z7dnOduqEow/giphy.gif",
                ],
                "messages": [
                    "{author} đã vỗ đầu {target}! 👋",
                    "{author} đang pat {target}! 🥰",
                    "{author} vừa vỗ nhẹ đầu {target}! ✨",
                    "{author} đã pat pat {target}! 💕",
                ]
            },
            "slap": {
                "gifs": [
                    "https://media.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif",
                    "https://media.giphy.com/media/tX29X2Dx3sAXS/giphy.gif",
                    "https://media.giphy.com/media/xUO4t2gkWBxDi/giphy.gif",
                    "https://media.giphy.com/media/jLeyZWgtwgr2U/giphy.gif",
                    "https://media.giphy.com/media/mXnO9IiWWarkI/giphy.gif",
                ],
                "messages": [
                    "{author} đã tát {target}! 👋",
                    "{author} vừa slap {target}! 😤",
                    "{author} đã cho {target} một cái tát! 💢",
                    "{author} đã đánh {target}! 😠",
                ]
            },
            "cuddle": {
                "gifs": [
                    "https://media.giphy.com/media/PHZ7v9tfQu0o0/giphy.gif",
                    "https://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif",
                    "https://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif",
                    "https://media.giphy.com/media/wnsgren9NtITS/giphy.gif",
                    "https://media.giphy.com/media/svXXBgduBsJ20/giphy.gif",
                ],
                "messages": [
                    "{author} đang âu yếm {target}! 🥰",
                    "{author} đã cuddle {target}! 💕",
                    "{author} vừa ôm ấp {target}! ❤️",
                    "{author} đang nựng {target}! 😊",
                ]
            },
            "poke": {
                "gifs": [
                    "https://media.giphy.com/media/pHYaWbspekVsTKRFQT/giphy.gif",
                    "https://media.giphy.com/media/ROF8OQvDmxytW/giphy.gif",
                    "https://media.giphy.com/media/AXorq76Tg3Vte/giphy.gif",
                    "https://media.giphy.com/media/TlK63EHvdTL2sGjBfVK/giphy.gif",
                    "https://media.giphy.com/media/pWD3yJSfPCP0k/giphy.gif",
                ],
                "messages": [
                    "{author} đã chọc {target}! 👉",
                    "{author} vừa poke {target}! 😄",
                    "{author} đang chọc chọc {target}! 😆",
                    "{author} đã chọc vào {target}! 👈",
                ]
            },
            "lick": {
                "gifs": [
                    "https://media.giphy.com/media/lp3GUtG2waC88/giphy.gif",
                    "https://media.giphy.com/media/AEMyf9Oj6MpS8/giphy.gif",
                    "https://media.giphy.com/media/bm2O3nXTcKJeU/giphy.gif",
                    "https://media.giphy.com/media/3o7TKqnN349PBUtGFO/giphy.gif",
                    "https://media.giphy.com/media/Wq0p5iLiJbGzC/giphy.gif",
                ],
                "messages": [
                    "{author} đã liếm {target}! 👅",
                    "{author} vừa lick {target}! 😋",
                    "{author} đang liếm {target}! 😝",
                    "{author} đã liếm liếm {target}! 💦",
                ]
            },
            "bite": {
                "gifs": [
                    "https://media.giphy.com/media/TlK63EWmHJhXYu6rMVW/giphy.gif",
                    "https://media.giphy.com/media/Xh1vgIUkJBTdS/giphy.gif",
                    "https://media.giphy.com/media/TlK63EWmHJhXYu6rMVW/giphy.gif",
                    "https://media.giphy.com/media/7T5wldGkk7XgCyuNUK/giphy.gif",
                    "https://media.giphy.com/media/KB2yuELA5zYRy/giphy.gif",
                ],
                "messages": [
                    "{author} đã cắn {target}! 🦷",
                    "{author} vừa bite {target}! 😈",
                    "{author} đang cắn {target}! 😤",
                    "{author} đã cắn nhẹ {target}! 😏",
                ]
            },
            "punch": {
                "gifs": [
                    "https://media.giphy.com/media/j5QcmXoFWl4Q0/giphy.gif",
                    "https://media.giphy.com/media/1cXNQx80CEKmQ/giphy.gif",
                    "https://media.giphy.com/media/Gf3AUz3eBNbTW/giphy.gif",
                    "https://media.giphy.com/media/xUO4t2gkWBxDi/giphy.gif",
                    "https://media.giphy.com/media/mXnO9IiWWarkI/giphy.gif",
                ],
                "messages": [
                    "{author} đã đấm {target}! 👊",
                    "{author} vừa punch {target}! 💥",
                    "{author} đang đánh {target}! 😠",
                    "{author} đã cho {target} một cú đấm! 🥊",
                ]
            },
            "tickle": {
                "gifs": [
                    "https://media.giphy.com/media/pHYaWbspekVsTKRFQT/giphy.gif",
                    "https://media.giphy.com/media/ROF8OQvDmxytW/giphy.gif",
                    "https://media.giphy.com/media/AXorq76Tg3Vte/giphy.gif",
                    "https://media.giphy.com/media/TlK63EHvdTL2sGjBfVK/giphy.gif",
                    "https://media.giphy.com/media/pWD3yJSfPCP0k/giphy.gif",
                ],
                "messages": [
                    "{author} đang cù {target}! 🤭",
                    "{author} vừa tickle {target}! 😆",
                    "{author} đang cù lét {target}! 😂",
                    "{author} đã cù {target}! 🤣",
                ]
            },
            "highfive": {
                "gifs": [
                    "https://media.giphy.com/media/lLkKpUBx8K6be/giphy.gif",
                    "https://media.giphy.com/media/g5R9dok94mrIvplmZd/giphy.gif",
                    "https://media.giphy.com/media/DKnMqdm9i980E/giphy.gif",
                    "https://media.giphy.com/media/3oEjHV0z8S7WM4MwnK/giphy.gif",
                    "https://media.giphy.com/media/10LKovKon8DENq/giphy.gif",
                ],
                "messages": [
                    "{author} đã highfive {target}! ✋",
                    "{author} vừa vỗ tay với {target}! 🙌",
                    "{author} đang highfive {target}! 🎉",
                    "{author} đã击掌 với {target}! ⚡",
                ]
            },
            "boop": {
                "gifs": [
                    "https://media.giphy.com/media/pHYaWbspekVsTKRFQT/giphy.gif",
                    "https://media.giphy.com/media/ROF8OQvDmxytW/giphy.gif",
                    "https://media.giphy.com/media/AXorq76Tg3Vte/giphy.gif",
                    "https://media.giphy.com/media/TlK63EHvdTL2sGjBfVK/giphy.gif",
                    "https://media.giphy.com/media/pWD3yJSfPCP0k/giphy.gif",
                ],
                "messages": [
                    "{author} đã boop mũi {target}! 👃",
                    "{author} vừa chạm mũi {target}! 😊",
                    "{author} đang boop {target}! 🥰",
                    "{author} đã boop boop {target}! ✨",
                ]
            },
            "wave": {
                "gifs": [
                    "https://media.giphy.com/media/DKnMqdm9i980E/giphy.gif",
                    "https://media.giphy.com/media/3oEjHV0z8S7WM4MwnK/giphy.gif",
                    "https://media.giphy.com/media/10LKovKon8DENq/giphy.gif",
                    "https://media.giphy.com/media/lLkKpUBx8K6be/giphy.gif",
                    "https://media.giphy.com/media/g5R9dok94mrIvplmZd/giphy.gif",
                ],
                "messages": [
                    "{author} đang vẫy tay với {target}! 👋",
                    "{author} vừa wave {target}! 😊",
                    "{author} đã chào {target}! 🙋",
                    "{author} đang vẫy vẫy {target}! ✨",
                ]
            },
            "nom": {
                "gifs": [
                    "https://media.giphy.com/media/lp3GUtG2waC88/giphy.gif",
                    "https://media.giphy.com/media/AEMyf9Oj6MpS8/giphy.gif",
                    "https://media.giphy.com/media/bm2O3nXTcKJeU/giphy.gif",
                    "https://media.giphy.com/media/3o7TKqnN349PBUtGFO/giphy.gif",
                    "https://media.giphy.com/media/Wq0p5iLiJbGzC/giphy.gif",
                ],
                "messages": [
                    "{author} đang nom nom {target}! 😋",
                    "{author} vừa ăn {target}! 🍴",
                    "{author} đang nom {target}! 😝",
                    "{author} đã nom nom nom {target}! 🤤",
                ]
            },
            "stare": {
                "gifs": [
                    "https://media.giphy.com/media/pHYaWbspekVsTKRFQT/giphy.gif",
                    "https://media.giphy.com/media/ROF8OQvDmxytW/giphy.gif",
                    "https://media.giphy.com/media/AXorq76Tg3Vte/giphy.gif",
                    "https://media.giphy.com/media/TlK63EHvdTL2sGjBfVK/giphy.gif",
                    "https://media.giphy.com/media/pWD3yJSfPCP0k/giphy.gif",
                ],
                "messages": [
                    "{author} đang nhìn chằm chằm {target}! 👀",
                    "{author} vừa stare {target}! 😳",
                    "{author} đang dòm {target}! 👁️",
                    "{author} đã nhìn {target} không chớp mắt! 😶",
                ]
            },
        }
    
    def get_interaction(self, action: str, author: str, target: str) -> tuple:
        """
        Get random GIF and message for interaction
        Returns: (gif_url, message)
        """
        if action not in self.interactions:
            return None, None
        
        data = self.interactions[action]
        gif = random.choice(data["gifs"])
        message_template = random.choice(data["messages"])
        message = message_template.format(author=author, target=target)
        
        return gif, message
    
    def get_available_interactions(self) -> List[str]:
        """Get list of available interaction commands"""
        return list(self.interactions.keys())

# Global instance
interaction_system = InteractionCommands()
