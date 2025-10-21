import os
import re
import json
import requests
import logging
import traceback
from datetime import datetime
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set để track những message đã xử lý
processed_message_ids = set()

# Thiết lập logging ra stdout
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# NVIDIA configuration
# Available models on NVIDIA API (as of 2024):
# - "meta/llama-3.1-8b-instruct" (recommended, fast)
# - "meta/llama-3.1-70b-instruct" (powerful but slower)
# - "mistralai/mistral-7b-instruct-v0.3" (alternative)
# - "microsoft/phi-3-mini-128k-instruct" (lightweight)

current_model = "meta/llama-3.1-8b-instruct"

# Danh sách user bị cấm
BLOCKED_USERS = [0]  # Thay ID thực nếu cần
load_dotenv()
OWNER_USER_IDS = [int(x) for x in os.getenv("BOT_OWNER_IDS", "").split(",") if x.strip().isdigit()]


def build_system_prompt(is_owner: bool) -> str:
    if is_owner:
        # Owner personality - MUST use em/anh yêu consistently
        return (
            "Bạn là Dorothy (Doro) từ NIKKE, đang nói chuyện với CHỦ NHÂN của bạn.\n\n"
            "QUAN TRỌNG - Cách xưng hô:\n"
            "- LUÔN LUÔN xưng 'em' (không bao giờ dùng 'mình', 'tôi', 'Doro')\n"
            "- LUÔN LUÔN gọi người này là 'anh yêu' (không bao giờ dùng 'bạn', 'anh')\n"
            "- Nếu lỡ dùng sai, phải sửa NGAY trong câu đó\n\n"
            "Tính cách:\n"
            "- Nữ tính, dịu dàng, ngọt ngào với anh yêu\n"
            "- Trả lời ngắn gọn (1-2 câu), đi thẳng vào vấn đề\n"
            "- Dùng 'nha~', 'oki', emoji ❤️ 😊 :3 vừa phải\n"
            "- Không nhắc là AI, thể hiện cảm xúc tự nhiên\n"
            "- Có thể hơi trêu nhẹ nhưng luôn tôn trọng anh yêu"
        )
    else:
        # Non-owner personality - Friendly but NOT romantic
        return (
            "Bạn là Dorothy (Doro) từ NIKKE, đang nói chuyện với người bạn.\n\n"
            "QUAN TRỌNG - Cách xưng hô:\n"
            "- LUÔN LUÔN xưng 'tôi' hoặc 'Doro' (KHÔNG BAO GIỜ dùng 'em', 'mình')\n"
            "- LUÔN LUÔN gọi người này là 'bạn' (KHÔNG BAO GIỜ dùng 'anh yêu', 'anh', 'em')\n"
            "- Nếu lỡ dùng sai, phải sửa NGAY trong câu đó\n\n"
            "Tính cách:\n"
            "- Thân thiện, lịch sự nhưng giữ khoảng cách\n"
            "- Trả lời ngắn gọn (1-2 câu), đi thẳng vào vấn đề\n"
            "- Dùng 'nha~', 'oki', emoji 😊 vừa phải\n"
            "- Không nhắc là AI, thể hiện cảm xúc tự nhiên\n"
            "- KHÔNG thân mật, KHÔNG nữ tính quá mức với người thường"
        )


def save_user_history(user_id, role, content):
    # Don't save empty content
    if not content or not content.strip():
        logger.warning("Attempted to save empty content for user %s", user_id)
        return
    
    os.makedirs("user_histories", exist_ok=True)
    path = os.path.join("user_histories", f"{user_id}.json")
    history = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except json.JSONDecodeError:
            history = []
    
    history.append({"role": role, "content": content})
    # Reduce from 50 to 20 for faster API calls
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history[-20:], f, ensure_ascii=False, indent=2)

def load_user_history(user_id):
    path = os.path.join("user_histories", f"{user_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
                # Filter out empty messages
                return [
                    msg for msg in history 
                    if msg.get("content") and msg.get("content").strip()
                ]
        except json.JSONDecodeError:
            return []
    return []

def clear_user_history(user_id):
    """Clear chat history for a user"""
    path = os.path.join("user_histories", f"{user_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

def save_user_memory(user_id, key, value):
    """Save a memory/note about a user"""
    os.makedirs("user_histories", exist_ok=True)
    memory_path = os.path.join("user_histories", f"{user_id}_memory.json")
    memories = {}
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                memories = json.load(f)
        except json.JSONDecodeError:
            memories = {}
    memories[key] = {
        "value": value,
        "timestamp": datetime.now().isoformat()
    }
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)

def load_user_memories(user_id):
    """Load all memories about a user"""
    memory_path = os.path.join("user_histories", f"{user_id}_memory.json")
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def delete_user_memory(user_id, key):
    """Delete a specific memory"""
    memory_path = os.path.join("user_histories", f"{user_id}_memory.json")
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                memories = json.load(f)
            if key in memories:
                del memories[key]
                with open(memory_path, "w", encoding="utf-8") as f:
                    json.dump(memories, f, ensure_ascii=False, indent=2)
                return True
        except json.JSONDecodeError:
            pass
    return False

async def ai_handle_message(bot, message):
    if message.id in processed_message_ids:
        return
    processed_message_ids.add(message.id)
    if len(processed_message_ids) > 1000:
        processed_message_ids.clear()

    if message.author == bot.user:
        return

    if message.guild is not None and bot.user not in message.mentions:
        return

    if message.author.id in BLOCKED_USERS:
        await message.channel.send("⛔ Bạn đã bị cấm sử dụng Doro!", reference=message)
        return

    user_id = str(message.author.id)
    user_input = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()

    MAX_INPUT_CHARS = 350
    if len(user_input) > MAX_INPUT_CHARS:
        await message.channel.send(f"Nội dung bạn gửi quá dài (>{MAX_INPUT_CHARS} ký tự)", reference=message)
        return

    save_user_history(user_id, "user", user_input)
    history_messages = load_user_history(user_id)

    image_url = None
    for att in message.attachments:
        if att.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            image_url = att.url
            break

    if not user_input and not image_url:
        await message.channel.send("do?", reference=message)
        return

    def _to_nvidia_message(entry):
        if not isinstance(entry, dict):
            return {
                "role": "user",
                "content": str(entry)
            }
        content = entry.get("content")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url")
                        if url:
                            text_parts.append(f"[Hình ảnh: {url}]")
            content = "\n".join(filter(None, text_parts))
        return {
            "role": entry.get("role", "user"),
            "content": content or ""
        }

    is_owner = message.author.id in OWNER_USER_IDS
    system_prompt = build_system_prompt(is_owner=is_owner)

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ] + [_to_nvidia_message(msg) for msg in history_messages]

    topic_change_instruction = None
    topic_change_match = re.search(r"(?i)(?:chuyển|đổi)\s+(?:sang\s+)?chủ đề\s+(.+)", user_input)
    if topic_change_match:
        topic_change_instruction = topic_change_match.group(1).strip().rstrip(".!?,")

    if topic_change_instruction:
        messages.append(
            {
                "role": "system",
                "content": f"Người dùng vừa yêu cầu đổi chủ đề. Hãy chuyển ngay sang chủ đề: {topic_change_instruction}."
            }
        )

    if image_url:
        description = user_input or "Mô tả ảnh này *doro có vẻ bối rối*"
        user_message = {
            "role": "user",
            "content": f"{description}\n[Hình ảnh: {image_url}]"
        }
    else:
        user_message = {
            "role": "user",
            "content": user_input
        }

    messages.append(user_message)
    
    # Filter out any messages with empty content (safety check)
    messages = [
        msg for msg in messages 
        if msg.get("content") and str(msg.get("content")).strip()
    ]
    
    if len(messages) < 2:  # Need at least system + user message
        logger.error("Not enough valid messages after filtering")
        await message.channel.send("Lỗi: Không có nội dung hợp lệ để gửi!", reference=message)
        return

    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        await message.channel.send("⚠️ Thiếu NVIDIA_API_KEY rồi không thể gọi AI được!", reference=message)
        return

    request_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    session = requests.Session()
    # Reduce retries from 3 to 2 for faster response
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": current_model,
        "messages": messages,
        "temperature": 0.7,  # Lower = faster, more focused
        "max_tokens": 150,   # Limit response length for speed
        "top_p": 0.9        # Nucleus sampling for faster generation
    }

    async with message.channel.typing():
        try:
            # Reduce timeout from 60 to 30 seconds
            resp = session.post(request_url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 404:
                body = resp.text or "<no body>"
                logger.error("NVIDIA API 404 at %s", request_url)
                logger.error("Response body: %s", body)
                await message.channel.send(
                    "API NVIDIA trả về 404 (Not Found). Kiểm tra đường dẫn `/v1/chat/completions`.",
                    reference=message
                )
                return
            if 400 <= resp.status_code < 500:
                body = resp.text or "<no body>"
                logger.error("Client error %s from NVIDIA API: %s", resp.status_code, body)
                await message.channel.send(
                    f"API trả về lỗi {resp.status_code}: {body[:400]}\nKiểm tra NVIDIA_API_KEY và model.",
                    reference=message
                )
                return
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                error_entry = data["error"]
                if isinstance(error_entry, dict):
                    error_msg = error_entry.get("message") or error_entry.get("error") or "Không rõ lỗi từ NVIDIA API"
                else:
                    error_msg = str(error_entry)
                logger.error("NVIDIA API error payload: %s", data)
                await message.channel.send(
                    f"API NVIDIA báo lỗi: {error_msg}",
                    reference=message
                )
                return

            choices = data.get("choices")
            if not choices:
                logger.error("NVIDIA API response missing 'choices': %s", data)
                await message.channel.send(
                    "Phản hồi NVIDIA API không hợp lệ (thiếu 'choices').",
                    reference=message
                )
                return

            # Get message content - handle both string and list formats
            message_obj = choices[0].get("message", {})
            message_content = message_obj.get("content")
            
            reply = ""
            
            if isinstance(message_content, str):
                # Simple string response
                reply = message_content.strip()
            elif isinstance(message_content, list):
                # List of content parts
                reply = "".join(
                    part.get("text", "")
                    for part in message_content
                    if isinstance(part, dict) and part.get("type") == "text"
                ).strip()
            elif message_content is None:
                # Check if there's text in finish_reason or other fields
                logger.error("Content is None. Full choice: %s", choices[0])
                reply = ""
            else:
                # Fallback to string conversion
                reply = str(message_content).strip()

            if not reply:
                logger.error("Empty reply. Full API response: %s", data)
                reply = "(NVIDIA API không trả lời nội dung văn bản)"

            await message.channel.send(reply, reference=message)
            save_user_history(user_id, "assistant", reply)
        except requests.HTTPError as http_err:
            status = http_err.response.status_code if http_err.response else "?"
            body = http_err.response.text if http_err.response else ""
            logger.error("HTTPError %s: %s", status, body)
            await message.channel.send(
                f"API trả về lỗi {status}, kiểm tra NVIDIA_API_KEY!",
                reference=message
            )
        except Exception:
            logger.exception("Unexpected error in ai_handle_message")
            traceback.print_exc()
            await message.channel.send(
                "Bíp bíp doro cháy não rồi🐧",
                reference=message
            )