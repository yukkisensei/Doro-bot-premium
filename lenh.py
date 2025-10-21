import asyncio
import logging
import os
import re
import shutil
import urllib.parse
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Dict, Optional

import discord
from discord.ext import commands
import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

import ai
from economy import economy
from afk_system import afk_system
from command_disable import disable_system
from profile_card import profile_card_generator
from interactions import interaction_system
from shop_system import shop_system
from marriage_system import marriage_system


OWNER_IDS = [int(x) for x in os.getenv("BOT_OWNER_IDS", "").split(",") if x.strip().isdigit()]

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "default_search": "scsearch1",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

_FFMPEG_EXEC: Optional[str] = None
_FFMPEG_HINTS = [
    r"C:\\ffmpeg\\bin\\ffmpeg.exe",
    r"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
    r"C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
]


def resolve_ffmpeg_path() -> Optional[str]:
    global _FFMPEG_EXEC

    if _FFMPEG_EXEC and os.path.exists(_FFMPEG_EXEC):
        return _FFMPEG_EXEC

    candidates = []
    env_path = os.getenv("FFMPEG_PATH")
    if env_path:
        cleaned = env_path.strip().strip('"')
        if cleaned:
            candidates.append(cleaned)

    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    candidates.extend(hint for hint in _FFMPEG_HINTS if os.path.exists(hint))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            _FFMPEG_EXEC = candidate
            return _FFMPEG_EXEC

    _FFMPEG_EXEC = None
    return None


@dataclass
class MusicTrack:
    title: str
    stream_url: str
    webpage_url: str


@dataclass
class MusicState:
    queue: Deque[MusicTrack] = field(default_factory=deque)
    voice_client: Optional[discord.VoiceClient] = None
    now_playing: Optional[MusicTrack] = None
    stay_mode: bool = False
    text_channel: Optional[discord.abc.Messageable] = None
    auto_leave_task: Optional[asyncio.Task] = None
    loop_mode: str = "off"  # "off", "one", "all"
    volume: float = 1.0
    play_history: Deque[MusicTrack] = field(default_factory=lambda: deque(maxlen=50))


def setup(bot_instance: commands.Bot) -> None:
    global bot
    bot = bot_instance
    
    # Add check for disabled commands
    @bot.check
    async def check_command_disabled(ctx: commands.Context):
        # Skip check for DMs
        if not ctx.guild:
            return True
        
        # Skip check for owners
        if ctx.author.id in OWNER_IDS:
            return True
        
        # Check if command is disabled in this channel
        channel_id = str(ctx.channel.id)
        command_name = ctx.command.name if ctx.command else None
        
        if command_name and disable_system.is_disabled(channel_id, command_name):
            # Silently ignore - don't respond
            return False
        
        return True

    music_states: Dict[int, MusicState] = {}

    def get_state(guild_id: int) -> MusicState:
        state = music_states.get(guild_id)
        if state is None:
            state = MusicState()
            music_states[guild_id] = state
        return state

    def cancel_auto_leave(state: MusicState) -> None:
        if state.auto_leave_task and not state.auto_leave_task.done():
            state.auto_leave_task.cancel()
        state.auto_leave_task = None

    def schedule_auto_leave(guild_id: int) -> None:
        state = music_states.get(guild_id)
        if not state:
            return
        cancel_auto_leave(state)

        async def _delayed_leave() -> None:
            try:
                await asyncio.sleep(120)
            except asyncio.CancelledError:
                return

            state_after = music_states.get(guild_id)
            if not state_after:
                return
            if state_after.stay_mode:
                state_after.auto_leave_task = None
                return

            voice_client_after = state_after.voice_client
            if not voice_client_after or state_after.queue or state_after.now_playing:
                state_after.auto_leave_task = None
                return

            if not voice_client_after.is_connected():
                state_after.auto_leave_task = None
                return

            try:
                await voice_client_after.disconnect()
            except discord.HTTPException:
                logging.warning("Không disconnect được voice client ở guild %s", guild_id)
            else:
                state_after.voice_client = None
                state_after.now_playing = None
                if state_after.text_channel:
                    await state_after.text_channel.send("không thấy ai gọi nên tớ out ròi nhé do!")
            state_after.auto_leave_task = None

        state.auto_leave_task = bot.loop.create_task(_delayed_leave())

    async def ensure_voice(ctx: commands.Context) -> Optional[discord.VoiceClient]:
        if ctx.guild is None:
            await ctx.reply("Lệnh này chỉ dùng trong server thôi nha~", mention_author=False)
            return None
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("Vào voice rồi gọi em phát nhạc nha~", mention_author=False)
            return None

        channel = ctx.author.voice.channel
        voice_client = ctx.voice_client

        try:
            if voice_client:
                if voice_client.channel != channel:
                    await voice_client.move_to(channel)
            else:
                voice_client = await channel.connect()
        except discord.Forbidden:
            await ctx.reply("Em thiếu quyền vào voice đó :<", mention_author=False)
            return None
        except discord.HTTPException:
            await ctx.reply("Discord đang lag nên em chưa vào voice được, thử lại giúp em nha~", mention_author=False)
            return None

        state = get_state(ctx.guild.id)
        state.voice_client = voice_client
        state.text_channel = ctx.channel
        cancel_auto_leave(state)
        return voice_client

    async def extract_track(query: str) -> MusicTrack:
        raw_query = query.strip()
        if not raw_query:
            raise ValueError("Thiếu từ khóa tìm nhạc.")

        search = raw_query
        # Decode repeatedly to eliminate nested percent-encoding from embeds/API urls
        while True:
            decoded = urllib.parse.unquote(search)
            if decoded == search:
                break
            search = decoded

        track_id: Optional[str] = None

        match = re.search(r"(?:soundcloud:)?tracks?:(\d+)", search)
        if match:
            track_id = match.group(1)
        elif search.startswith("https://api.soundcloud.com/tracks/"):
            tail = search.rsplit("/", 1)[-1]
            if tail.isdigit():
                track_id = tail

        candidates: list[str] = []

        def add_candidate(value: Optional[str]) -> None:
            if value and value not in candidates:
                candidates.append(value)

        if track_id:
            add_candidate(f"https://api.soundcloud.com/tracks/{track_id}")
            add_candidate(f"scsearch1:{track_id}")
            add_candidate(f"scsearch1:soundcloud track {track_id}")
        else:
            if search.startswith(("http://", "https://")):
                add_candidate(search)
            else:
                add_candidate(f"scsearch1:{search}")

        logging.debug("SoundCloud candidates for '%s': %s", raw_query, candidates)

        loop = asyncio.get_event_loop()

        def _parse_id_from_error(error: Exception) -> Optional[str]:
            message = str(getattr(error, "msg", None) or error)
            match = re.search(r"soundcloud%3Atracks%3A(\d+)", message)
            if match:
                return match.group(1)
            return None

        def _add_retry_candidates(track_num: str) -> None:
            add_candidate(f"https://api.soundcloud.com/tracks/{track_num}")
            add_candidate(f"scsearch1:{track_num}")
            add_candidate(f"scsearch1:soundcloud track {track_num}")

        def _resolve_entry(entry: Dict) -> Optional[Dict]:
            if not entry:
                return None

            entry_url = entry.get("url")
            entry_id = entry.get("id")

            candidates_to_try: list[str] = []

            if entry_id and str(entry_id).isdigit():
                candidates_to_try.append(f"https://api.soundcloud.com/tracks/{entry_id}")

            if entry_url:
                decoded_entry_url = urllib.parse.unquote(entry_url)
                match = re.search(r"(?:soundcloud:)?tracks?:(\d+)", decoded_entry_url)
                if match:
                    candidates_to_try.append(f"https://api.soundcloud.com/tracks/{match.group(1)}")
                if entry_url.startswith(("http://", "https://")):
                    candidates_to_try.append(entry_url)

            for candidate_url in candidates_to_try:
                try:
                    return ytdl.extract_info(candidate_url, download=False)
                except (DownloadError, ExtractorError):
                    continue

            # Nếu entry đã có formats, trả về nguyên entry để xử lý tiếp
            if entry.get("formats"):
                return entry

            return None

        def _extract():
            attempted: set[str] = set()
            queue: Deque[str] = deque(candidates)
            last_error: Optional[Exception] = None

            while queue:
                candidate = queue.popleft()
                if candidate in attempted:
                    continue
                attempted.add(candidate)

                logging.debug("Trying SoundCloud candidate: %s", candidate)
                try:
                    info = ytdl.extract_info(candidate, download=False)
                except (DownloadError, ExtractorError) as exc:
                    last_error = exc
                    new_id = _parse_id_from_error(exc)
                    if new_id:
                        _add_retry_candidates(new_id)
                        for extra_candidate in list(candidates):
                            if extra_candidate not in attempted:
                                queue.append(extra_candidate)
                    continue

                if "entries" in info:
                    for entry in info["entries"]:
                        resolved = _resolve_entry(entry)
                        if resolved:
                            return resolved
                    continue

                return info

            if last_error is not None:
                raise last_error

            raise ValueError("Không tìm thấy kết quả SoundCloud nào hợp lệ.")

        try:
            info = await loop.run_in_executor(None, _extract)
        except (DownloadError, ExtractorError) as exc:
            raise ValueError(str(exc)) from exc

        stream_url: Optional[str] = info.get("url")

        if not stream_url or stream_url.startswith("soundcloud:"):
            formats = info.get("formats") or []
            # ưu tiên audio progressive để FFMPEG chơi dễ
            def sort_key(fmt: Dict) -> int:
                proto = fmt.get("protocol") or ""
                preference = fmt.get("preference", 0)
                # ưu tiên http > hls > others
                proto_score = {
                    "http": 3,
                    "https": 3,
                    "progressive": 3,
                    "hls": 2,
                    "m3u8": 2,
                    "m3u8_native": 2,
                }.get(proto, 1)
                return (preference, proto_score, fmt.get("abr") or 0)

            if not formats:
                raise ValueError("Không tìm thấy stream SoundCloud hợp lệ cho bài này.")

            best = max(formats, key=sort_key)
            stream_url = best.get("url")

        if not stream_url or stream_url.startswith("soundcloud:"):
            raise ValueError("Không lấy được stream SoundCloud hợp lệ sau khi thử nhiều định dạng.")

        title = info.get("title", "SoundCloud track")
        webpage_url = info.get("webpage_url") or info.get("original_url") or search
        return MusicTrack(title=title, stream_url=stream_url, webpage_url=webpage_url)

    async def play_next(guild_id: int) -> None:
        state = music_states.get(guild_id)
        voice_client = state.voice_client if state else None
        if not state or not voice_client:
            return

        cancel_auto_leave(state)

        # Handle loop mode
        if state.loop_mode == "one" and state.now_playing:
            track = state.now_playing
        elif not state.queue:
            if state.loop_mode == "all" and state.play_history:
                # Reload queue from history
                state.queue = deque(state.play_history)
                track = state.queue.popleft()
            else:
                state.now_playing = None
                if not state.stay_mode and voice_client.is_connected():
                    schedule_auto_leave(guild_id)
                return
        else:
            track = state.queue.popleft()

        # Add to history if not looping one song
        if state.loop_mode != "one":
            state.play_history.append(track)
        
        state.now_playing = track

        ffmpeg_exec = resolve_ffmpeg_path()
        if not ffmpeg_exec:
            logging.error("Không tìm thấy FFmpeg khi phát tại guild %s", guild_id)
            state.queue.appendleft(track)
            if state.text_channel:
                await state.text_channel.send(
                    "Không tìm thấy FFmpeg. Cài thêm hoặc đặt biến `FFMPEG_PATH` giúp em nha~"
                )
            return

        def after_play(error: Optional[Exception]) -> None:
            asyncio.run_coroutine_threadsafe(handle_after(guild_id, error), bot.loop)

        source = discord.FFmpegPCMAudio(track.stream_url, executable=ffmpeg_exec, **FFMPEG_OPTIONS)
        # Apply volume
        source = discord.PCMVolumeTransformer(source, volume=state.volume)
        
        try:
            voice_client.play(source, after=after_play)
        except discord.ClientException as exc:
            logging.error("Không thể phát tại guild %s: %s", guild_id, exc)
            state.queue.appendleft(track)
            return

        if state.text_channel:
            loop_emoji = ""
            if state.loop_mode == "one":
                loop_emoji = " 🔂"
            elif state.loop_mode == "all":
                loop_emoji = " 🔁"
            await state.text_channel.send(f"Đang phát **{track.title}** 🎶{loop_emoji} ({track.webpage_url})")

    async def handle_after(guild_id: int, error: Optional[Exception]) -> None:
        state = music_states.get(guild_id)
        if state:
            state.now_playing = None
        if error:
            logging.error("Playback error tại guild %s: %s", guild_id, error)
        await play_next(guild_id)

    @bot.command(name="say", aliases=["speak"], help="Doro nói hộ bạn một câu")
    async def say(ctx: commands.Context, *, message: str) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        await ctx.send(message)

    @bot.command(name="sync", help="Sync slash commands (owner)")
    async def sync_commands(ctx: commands.Context) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        
        try:
            synced = await bot.tree.sync()
            await ctx.reply(f"✅ Đã sync {len(synced)} slash commands!", mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Lỗi khi sync: {e}", mention_author=False)
    
    @bot.command(name="model", help="Xem/đổi AI model (owner)")
    async def model_cmd(ctx: commands.Context, *, model_name: str = None) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        
        if model_name is None:
            # Show current model
            await ctx.reply(f"🤖 Model hiện tại: `{ai.current_model}`", mention_author=False)
        else:
            # Change model
            ai.current_model = model_name
            await ctx.reply(f"✅ Đã đổi model sang: `{model_name}`", mention_author=False)
    
    @bot.command(name="testpersonality", help="Test personality consistency (owner)")
    async def testpersonality_cmd(ctx: commands.Context) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        
        is_owner = ctx.author.id in OWNER_IDS
        prompt = ai.build_system_prompt(is_owner)
        
        embed = discord.Embed(
            title="🎭 Personality Test",
            description=f"**Is Owner:** {is_owner}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="System Prompt",
            value=f"```\n{prompt[:1000]}...\n```" if len(prompt) > 1000 else f"```\n{prompt}\n```",
            inline=False
        )
        
        if is_owner:
            embed.add_field(
                name="✅ Expected",
                value="Xưng: **em** | Gọi: **anh yêu**",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Expected",
                value="Xưng: **mình/Doro** | Gọi: **bạn**",
                inline=False
            )
        
        await ctx.reply(embed=embed, mention_author=False)

    @bot.command(name="ping", help="Kiểm tra độ trễ của bot (prefix)")
    async def ping_prefix(ctx: commands.Context) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        latency_ms = ctx.bot.latency * 1000
        await ctx.reply(f"pong~ `{latency_ms:.0f}ms` nha~", mention_author=False)

    def build_help_embed() -> discord.Embed:
        music_lines = [
            "`+play <từ khóa/link>` – Phát nhạc",
            "`+skip` – Bỏ qua bài",
            "`+pause/resume` – Tạm dừng/phát tiếp",
            "`+stop` – Dừng và xoá queue",
            "`+queue` – Xem hàng đợi",
            "`+np` – Bài đang phát",
            "`+loop [off/one/all]` – Lặp lại",
            "`+shuffle` – Xáo trộn queue",
            "`+volume <0-100>` – Âm lượng",
            "`+history` – Lịch sử phát"
        ]
        
        economy_lines = [
            "`+balance [@user]` – Xem số tiền",
            "`+daily` – Nhận thưởng hàng ngày",
            "`+deposit/withdraw <số>` – Gửi/rút bank",
            "`+give @user <số>` – Chuyển tiền",
            "`+stats [@user]` – Xem thống kê",
            "`+leaderboard` – Top giàu nhất"
        ]
        
        casino_lines = [
            "`+cf <heads/tails> <số>` – Coinflip bet",
            "`+slots <số>` – Slot machine",
            "`+bj <số>` – Blackjack",
            "`+tx <số>` – Tài xỉu (3 xúc xắc)"
        ]
        
        shop_lines = [
            "`+shop [category]` – Xem cửa hàng",
            "`+buy <item_id> [số]` – Mua vật phẩm",
            "`+inventory [@user]` – Xem túi đồ",
            "`+use <item_id>` – Dùng vật phẩm",
            "`+equip <item_id>` – Trang bị",
            "`+unequip <ring/pet>` – Gỡ trang bị",
            "`+sell <item_id> [số]` – Bán vật phẩm",
            "`+gift @user <item_id>` – Tặng quà"
        ]
        
        ai_lines = [
            "`+reset` – Xóa lịch sử chat",
            "`+remember <key> <value>` – Lưu thông tin",
            "`+recall [key]` – Xem thông tin đã lưu",
            "`+forget <key>` – Xóa thông tin"
        ]
        
        fun_lines = [
            "`+8ball <câu hỏi>` – Quả cầu thần kỳ",
            "`+roll <dice>` – Tung xúc xắc (vd: 2d6)",
            "`+coinflip` – Tung đồng xu",
            "`+rps <rock/paper/scissors>` – Oẳn tù tì"
        ]
        
        interaction_lines = [
            "`+kiss @user` – Hôn ai đó 💋",
            "`+hug @user` – Ôm ai đó 🤗",
            "`+pat @user` – Vỗ đầu 👋",
            "`+slap @user` – Tát 😤",
            "`+cuddle @user` – Âu yếm 🥰",
            "`+poke @user` – Chọc 👉",
            "`+lick @user` – Liếm 👅",
            "`+bite @user` – Cắn 🦷",
            "`+punch @user` – Đấm 👊",
            "`+tickle @user` – Cù 🤭",
            "`+highfive @user` – Vỗ tay ✋",
            "`+boop @user` – Boop mũi 👃",
            "`+wave @user` – Vẫy tay 👋",
            "`+nom @user` – Nom nom 😋",
            "`+stare @user` – Nhìn chằm chằm 👀"
        ]
        
        marriage_lines = [
            "`+marry @user` – Cầu hôn 💍",
            "`+accept` – Đồng ý lời cầu hôn ✅",
            "`+reject` – Từ chối lời cầu hôn ❌",
            "`+divorce` – Ly hôn 💔",
            "`+marriage [@user]` – Xem thông tin hôn nhân 💑"
        ]
        
        utility_lines = [
            "`+help` – Danh sách lệnh",
            "`+about [category]` – Thông tin vật phẩm 📖",
            "`+avatar [@user]` – Xem avatar",
            "`+serverinfo` – Thông tin server",
            "`+userinfo [@user]` – Thông tin user",
            "`+card [@user]` – Generate profile card",
            "`+afk [lý do]` – Đặt trạng thái AFK"
        ]
        
        admin_lines = [
            "`/disable` – Toggle lệnh (multi-select, owner)",
            "`/disabled` – Xem lệnh bị tắt",
            "`/clearall` – Xóa tất cả (owner)"
        ]

        embed = discord.Embed(
            title="🎵 Doro Command List",
            description="Mention @Doro để chat với AI nha~",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="🎶 Music", value="\n".join(music_lines), inline=False)
        embed.add_field(name="💰 Economy", value="\n".join(economy_lines), inline=False)
        embed.add_field(name="🎰 Casino", value="\n".join(casino_lines) if casino_lines else "No commands", inline=False)
        embed.add_field(name="🏪 Shop", value="\n".join(shop_lines) if shop_lines else "No commands", inline=False)
        embed.add_field(name="🤖 AI", value="\n".join(ai_lines) if ai_lines else "No commands", inline=False)
        embed.add_field(name="🎮 Fun", value="\n".join(fun_lines), inline=False)
        embed.add_field(name="💕 Interactions", value="\n".join(interaction_lines), inline=False)
        embed.add_field(name="💍 Marriage", value="\n".join(marriage_lines), inline=False)
        embed.add_field(name="⚙️ Utility", value="\n".join(utility_lines), inline=False)
        embed.add_field(name="🔧 Admin (Slash)", value="\n".join(admin_lines), inline=False)
        embed.set_footer(text="Dùng dấu + trước lệnh hoặc slash /help • Made with ❤️")
        return embed

    @bot.command(name="help", help="Xem danh sách lệnh")
    async def help_prefix(ctx: commands.Context) -> None:
        await ctx.reply(embed=build_help_embed(), mention_author=False)

    @bot.tree.command(name="help", description="Xem danh sách lệnh của Doro")
    async def help_slash(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_help_embed(), ephemeral=True)

    @bot.command(name="play", aliases=["p"], help="Phát nhạc SoundCloud hoặc thêm vào hàng đợi")
    async def play(ctx: commands.Context, *, query: str) -> None:
        voice_client = await ensure_voice(ctx)
        if voice_client is None:
            return

        try:
            track = await extract_track(query)
        except ValueError as exc:
            logging.exception("Không lấy được thông tin bài hát: %s", exc)
            return await ctx.reply("Em chưa tìm ra bài đó, thử keyword khác giúp em nha~", mention_author=False)

        state = get_state(ctx.guild.id)
        state.queue.append(track)
        state.text_channel = ctx.channel
        cancel_auto_leave(state)

        if voice_client.is_playing() or voice_client.is_paused():
            await ctx.reply(f"Đã thêm **{track.title}** vào hàng đợi ❤️", mention_author=False)
        else:
            await play_next(ctx.guild.id)

    @bot.command(name="skip", aliases=["s"], help="Bỏ qua bài đang phát")
    async def skip(ctx: commands.Context) -> None:
        state = music_states.get(ctx.guild.id)
        voice_client = ctx.voice_client
        if not state or not voice_client or not voice_client.is_connected():
            return await ctx.reply("Hiện em đâu có phát bài nào đâu nha~", mention_author=False)

        if not voice_client.is_playing():
            return await ctx.reply("Không có bài nào đang phát để skip hết~", mention_author=False)

        voice_client.stop()
        await ctx.reply("Đã skip nha!", mention_author=False)

    @bot.command(name="queue", aliases=["q"], help="Xem hàng đợi")
    async def queue_cmd(ctx: commands.Context) -> None:
        state = music_states.get(ctx.guild.id)
        if not state or (not state.queue and not state.now_playing):
            return await ctx.reply("Hàng đợi trống trơn nè~", mention_author=False)

        entries = []
        if state.now_playing:
            entries.append(f"**Đang phát:** {state.now_playing.title}")

        for idx, track in enumerate(state.queue, start=1):
            entries.append(f"{idx}. {track.title}")

        text = "\n".join(entries[:15])
        if len(entries) > 15:
            text += f"\n... và {len(entries) - 15} bài nữa"

        await ctx.reply(text, mention_author=False)

    @bot.command(name="pause", help="Tạm dừng nhạc")
    async def pause(ctx: commands.Context) -> None:
        voice_client = ctx.voice_client
        if not voice_client or not voice_client.is_playing():
            return await ctx.reply("Em đâu có phát bài nào để pause đâu~", mention_author=False)

        voice_client.pause()
        await ctx.reply("Đã pause nha~", mention_author=False)

    @bot.command(name="resume", help="Tiếp tục phát nhạc")
    async def resume(ctx: commands.Context) -> None:
        voice_client = ctx.voice_client
        if not voice_client or not voice_client.is_paused():
            return await ctx.reply("Không có bài nào tạm dừng để resume nha~", mention_author=False)

        voice_client.resume()
        await ctx.reply("Phát tiếp nè~", mention_author=False)

    @bot.command(name="stop", help="Dừng nhạc và xoá hàng đợi")
    async def stop(ctx: commands.Context) -> None:
        state = music_states.get(ctx.guild.id)
        voice_client = ctx.voice_client
        if state:
            state.queue.clear()
            state.now_playing = None

        if voice_client and voice_client.is_playing():
            voice_client.stop()

        await ctx.reply("Đã dừng và xoá hàng đợi nha~", mention_author=False)

    @bot.command(name="leave", aliases=["disconnect"], help="Đuổi Doro khỏi voice")
    async def leave(ctx: commands.Context) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        voice_client = ctx.voice_client
        if not voice_client or not voice_client.is_connected():
            return await ctx.reply("Em có ở trong voice đâu mà leave~", mention_author=False)

        await voice_client.disconnect()
        state = music_states.get(ctx.guild.id)
        if state:
            state.voice_client = None
            state.now_playing = None
            cancel_auto_leave(state)
        await ctx.reply("Em out voice rồi nè~", mention_author=False)

    @bot.command(name="stay", help="Bật/tắt chế độ ở lại voice sau khi hết nhạc")
    async def stay(ctx: commands.Context) -> None:
        state = get_state(ctx.guild.id)
        state.stay_mode = not state.stay_mode
        status = "bật" if state.stay_mode else "tắt"
        if state.stay_mode:
            cancel_auto_leave(state)
        await ctx.reply(f"Stay mode đã {status} nha~", mention_author=False)

    @bot.command(name="np", aliases=["nowplaying"], help="Xem bài đang phát")
    async def now_playing(ctx: commands.Context) -> None:
        state = music_states.get(ctx.guild.id)
        if not state or not state.now_playing:
            return await ctx.reply("Chưa có bài nào đang phát hết~", mention_author=False)

        track = state.now_playing
        await ctx.reply(f"Đang phát: **{track.title}**\n{track.webpage_url}", mention_author=False)

    @bot.command(name="move", help="Di chuyển một bài trong hàng đợi đến vị trí mới")
    async def move_track(ctx: commands.Context, current_index: int, new_index: int) -> None:
        state = music_states.get(ctx.guild.id)
        if not state or not state.queue:
            return await ctx.reply("Hàng đợi trống trơn nè~", mention_author=False)

        queue_list = list(state.queue)
        if current_index < 1 or current_index > len(queue_list):
            return await ctx.reply("Vị trí hiện tại không hợp lệ nha~", mention_author=False)

        new_index_clamped = max(1, min(new_index, len(queue_list)))
        track = queue_list.pop(current_index - 1)
        queue_list.insert(new_index_clamped - 1, track)
        state.queue = deque(queue_list)

        await ctx.reply(f"Đã chuyển **{track.title}** tới vị trí {new_index_clamped} nha~", mention_author=False)

    @bot.command(name="remove", aliases=["rm"], help="Xoá một bài khỏi hàng đợi")
    async def remove_track(ctx: commands.Context, index: int) -> None:
        state = music_states.get(ctx.guild.id)
        if not state or not state.queue:
            return await ctx.reply("Hàng đợi trống trơn nè~", mention_author=False)

        queue_list = list(state.queue)
        if index < 1 or index > len(queue_list):
            return await ctx.reply("Vị trí đó không có bài nào hết nha~", mention_author=False)

        removed_track = queue_list.pop(index - 1)
        state.queue = deque(queue_list)
        await ctx.reply(f"Đã xoá **{removed_track.title}** khỏi hàng đợi nha~", mention_author=False)

    @bot.command(name="loop", aliases=["repeat"], help="Bật/tắt chế độ lặp (off/one/all)")
    async def loop_cmd(ctx: commands.Context, mode: str = None) -> None:
        state = get_state(ctx.guild.id)
        
        if mode is None:
            # Cycle through modes
            if state.loop_mode == "off":
                state.loop_mode = "one"
                await ctx.reply("Đã bật lặp lại bài hiện tại 🔂", mention_author=False)
            elif state.loop_mode == "one":
                state.loop_mode = "all"
                await ctx.reply("Đã bật lặp lại toàn bộ hàng đợi 🔁", mention_author=False)
            else:
                state.loop_mode = "off"
                await ctx.reply("Đã tắt chế độ lặp ❌", mention_author=False)
        else:
            mode = mode.lower()
            if mode in ["off", "0", "none"]:
                state.loop_mode = "off"
                await ctx.reply("Đã tắt chế độ lặp ❌", mention_author=False)
            elif mode in ["one", "1", "single"]:
                state.loop_mode = "one"
                await ctx.reply("Đã bật lặp lại bài hiện tại 🔂", mention_author=False)
            elif mode in ["all", "queue", "2"]:
                state.loop_mode = "all"
                await ctx.reply("Đã bật lặp lại toàn bộ hàng đợi 🔁", mention_author=False)
            else:
                await ctx.reply("Chế độ không hợp lệ! Dùng: off/one/all", mention_author=False)

    @bot.command(name="shuffle", help="Xáo trộn hàng đợi")
    async def shuffle_cmd(ctx: commands.Context) -> None:
        state = music_states.get(ctx.guild.id)
        if not state or not state.queue:
            return await ctx.reply("Hàng đợi trống nên không shuffle được nha~", mention_author=False)

        import random
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = deque(queue_list)
        await ctx.reply(f"Đã xáo trộn {len(queue_list)} bài trong hàng đợi 🔀", mention_author=False)

    @bot.command(name="volume", aliases=["vol"], help="Điều chỉnh âm lượng (0-100)")
    async def volume_cmd(ctx: commands.Context, volume: int = None) -> None:
        state = get_state(ctx.guild.id)
        voice_client = ctx.voice_client
        
        if volume is None:
            current_vol = int(state.volume * 100)
            return await ctx.reply(f"Âm lượng hiện tại: **{current_vol}%** 🔊", mention_author=False)
        
        if volume < 0 or volume > 100:
            return await ctx.reply("Âm lượng phải từ 0 đến 100 nha~", mention_author=False)
        
        state.volume = volume / 100.0
        
        # Update current playing track volume
        if voice_client and voice_client.source:
            if isinstance(voice_client.source, discord.PCMVolumeTransformer):
                voice_client.source.volume = state.volume
        
        await ctx.reply(f"Đã đặt âm lượng thành **{volume}%** 🔊", mention_author=False)

    @bot.command(name="history", aliases=["hist"], help="Xem lịch sử phát nhạc")
    async def history_cmd(ctx: commands.Context) -> None:
        state = music_states.get(ctx.guild.id)
        if not state or not state.play_history:
            return await ctx.reply("Chưa có lịch sử phát nhạc nào nè~", mention_author=False)

        entries = []
        for idx, track in enumerate(reversed(list(state.play_history)), start=1):
            entries.append(f"{idx}. {track.title}")
            if idx >= 10:
                break

        text = "**Lịch sử phát nhạc (10 bài gần nhất):**\n" + "\n".join(entries)
        await ctx.reply(text, mention_author=False)

    @bot.command(name="reset", aliases=["clear"], help="Xóa lịch sử chat với AI")
    async def reset_ai(ctx: commands.Context) -> None:
        user_id = str(ctx.author.id)
        if ai.clear_user_history(user_id):
            await ctx.reply("Đã xóa lịch sử chat của bạn với em rồi nha~ 🗑️", mention_author=False)
        else:
            await ctx.reply("Bạn chưa có lịch sử chat nào với em cả~", mention_author=False)

    @bot.command(name="cleanhistory", help="Xóa messages rỗng trong history (owner)")
    async def cleanhistory_cmd(ctx: commands.Context) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        
        import os
        import json
        
        cleaned = 0
        history_dir = "user_histories"
        
        if not os.path.exists(history_dir):
            await ctx.reply("Không có history folder!", mention_author=False)
            return
        
        for filename in os.listdir(history_dir):
            if filename.endswith(".json") and not filename.endswith("_memory.json"):
                filepath = os.path.join(history_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        history = json.load(f)
                    
                    # Filter out empty messages
                    original_len = len(history)
                    cleaned_history = [
                        msg for msg in history
                        if msg.get("content") and msg.get("content").strip()
                    ]
                    
                    if len(cleaned_history) < original_len:
                        with open(filepath, "w", encoding="utf-8") as f:
                            json.dump(cleaned_history, f, ensure_ascii=False, indent=2)
                        cleaned += 1
                except Exception as e:
                    continue
        
        await ctx.reply(f"✅ Đã clean {cleaned} history files!", mention_author=False)

    @bot.command(name="remember", help="Lưu thông tin quan trọng")
    async def remember_cmd(ctx: commands.Context, key: str, *, value: str) -> None:
        user_id = str(ctx.author.id)
        ai.save_user_memory(user_id, key, value)
        await ctx.reply(f"Đã lưu **{key}**: {value} vào bộ nhớ của em rồi nha~ 💾", mention_author=False)

    @bot.command(name="recall", aliases=["memories"], help="Xem thông tin đã lưu")
    async def recall_cmd(ctx: commands.Context, key: str = None) -> None:
        user_id = str(ctx.author.id)
        memories = ai.load_user_memories(user_id)
        
        if not memories:
            return await ctx.reply("Em chưa lưu thông tin gì về bạn cả~", mention_author=False)
        
        if key:
            if key in memories:
                mem = memories[key]
                await ctx.reply(f"**{key}**: {mem['value']}", mention_author=False)
            else:
                await ctx.reply(f"Em không tìm thấy thông tin về **{key}** nha~", mention_author=False)
        else:
            entries = [f"**{k}**: {v['value']}" for k, v in memories.items()]
            text = "**Thông tin em nhớ về bạn:**\n" + "\n".join(entries[:10])
            if len(entries) > 10:
                text += f"\n... và {len(entries) - 10} thông tin khác"
            await ctx.reply(text, mention_author=False)

    @bot.command(name="forget", help="Xóa một thông tin đã lưu")
    async def forget_cmd(ctx: commands.Context, key: str) -> None:
        user_id = str(ctx.author.id)
        if ai.delete_user_memory(user_id, key):
            await ctx.reply(f"Đã xóa thông tin **{key}** rồi nha~ 🗑️", mention_author=False)
        else:
            await ctx.reply(f"Em không tìm thấy thông tin **{key}** để xóa~", mention_author=False)

    @bot.command(name="8ball", help="Hỏi quả cầu thần kỳ")
    async def eight_ball(ctx: commands.Context, *, question: str = None) -> None:
        if not question:
            return await ctx.reply("Bạn muốn hỏi gì nào? 🔮", mention_author=False)
        
        import random
        responses = [
            "Chắc chắn rồi! ✨",
            "Không nghi ngờ gì nữa~ 💯",
            "Chắc chắn là vậy nha! 😊",
            "Có vẻ khả quan đó~ ✨",
            "Dấu hiệu cho thấy là có~ 🌟",
            "Hỏi lại sau nha~ 🤔",
            "Em không chắc lắm... 😅",
            "Đừng tin vào điều đó~ ❌",
            "Câu trả lời của em là không 🙅‍♀️",
            "Rất khó xảy ra nha~ 😔",
            "Hmm... có thể~ 🤷‍♀️",
            "Em nghĩ là được đó! 💖",
            "Không nên kỳ vọng quá~ 😬",
            "Tương lai không rõ ràng lắm... 🌫️"
        ]
        answer = random.choice(responses)
        await ctx.reply(f"🔮 **{question}**\n{answer}", mention_author=False)

    @bot.command(name="roll", help="Tung xúc xắc (vd: 2d6, 1d20)")
    async def roll_dice(ctx: commands.Context, dice: str = "1d6") -> None:
        import random
        try:
            # Parse dice notation (e.g., 2d6 = 2 dice with 6 sides)
            match = re.match(r"(\d+)d(\d+)", dice.lower())
            if not match:
                return await ctx.reply("Định dạng không đúng! Dùng như: 1d6, 2d20, 3d12 nha~", mention_author=False)
            
            num_dice = int(match.group(1))
            num_sides = int(match.group(2))
            
            if num_dice < 1 or num_dice > 100:
                return await ctx.reply("Số xúc xắc phải từ 1 đến 100 nha~", mention_author=False)
            if num_sides < 2 or num_sides > 1000:
                return await ctx.reply("Số mặt phải từ 2 đến 1000 nha~", mention_author=False)
            
            rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
            total = sum(rolls)
            
            if num_dice == 1:
                await ctx.reply(f"🎲 Tung {dice}: **{total}**", mention_author=False)
            else:
                rolls_str = ", ".join(str(r) for r in rolls)
                await ctx.reply(f"🎲 Tung {dice}: [{rolls_str}] = **{total}**", mention_author=False)
        except Exception as e:
            await ctx.reply(f"Có lỗi xảy ra: {e}", mention_author=False)

    @bot.command(name="coinflip", aliases=["flip", "coin"], help="Tung đồng xu")
    async def coinflip(ctx: commands.Context) -> None:
        import random
        result = random.choice(["Ngửa 🪙", "Sấp 🪙"])
        await ctx.reply(f"Kết quả: **{result}**", mention_author=False)

    @bot.command(name="rps", help="Oẳn tù tì với Doro (rock/paper/scissors)")
    async def rock_paper_scissors(ctx: commands.Context, choice: str = None) -> None:
        if not choice:
            return await ctx.reply("Chọn rock (búa), paper (bao), hoặc scissors (kéo) nha~", mention_author=False)
        
        import random
        choices = {
            "rock": "🪨 Búa",
            "paper": "📄 Bao",
            "scissors": "✂️ Kéo",
            "búa": "🪨 Búa",
            "bao": "📄 Bao",
            "kéo": "✂️ Kéo",
            "r": "🪨 Búa",
            "p": "📄 Bao",
            "s": "✂️ Kéo"
        }
        
        user_choice = choice.lower()
        if user_choice not in choices:
            return await ctx.reply("Lựa chọn không hợp lệ! Chọn rock/paper/scissors nha~", mention_author=False)
        
        user_pick = choices[user_choice]
        bot_pick = random.choice(list(set(choices.values())))
        
        # Determine winner
        wins = {
            "🪨 Búa": "✂️ Kéo",
            "📄 Bao": "🪨 Búa",
            "✂️ Kéo": "📄 Bao"
        }
        
        if user_pick == bot_pick:
            result = "Hòa rồi! 🤝"
        elif wins[user_pick] == bot_pick:
            result = "Bạn thắng! 🎉"
        else:
            result = "Em thắng rồi~ 😊"
        
        await ctx.reply(f"Bạn chọn: {user_pick}\nEm chọn: {bot_pick}\n**{result}**", mention_author=False)
    
    # ==================== SHOP COMMANDS ====================
    
    @bot.command(name="shop", help="Xem cửa hàng 🏪")
    async def shop_cmd(ctx: commands.Context, category: str = None) -> None:
        if not category:
            # Show all categories
            embed = discord.Embed(
                title="🏪 SHOP - CỬA HÀNG",
                description="Chào mừng đến với cửa hàng Doro!\n\n**Cách dùng:** `+shop <category>`",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="📂 Categories",
                value="• `ring` - Nhẫn 💍 (1M-10M coins)\n• `pet` - Thú cưng 🐾\n• `lootbox` - Hộp quà 🎁\n• `consumable` - Vật phẩm tiêu hao 🍪\n• `collectible` - Vật phẩm sưu tầm 💎",
                inline=False
            )
            embed.set_footer(text="Ví dụ: +shop ring • Dùng +about <category> để xem chi tiết")
            return await ctx.reply(embed=embed, mention_author=False)
        
        category = category.lower()
        items = shop_system.get_shop_items(category)
        
        if not items:
            return await ctx.reply(f"❌ Không tìm thấy category `{category}`!", mention_author=False)
        
        # Create shop embed
        category_names = {
            "ring": "💍 NHẪN",
            "pet": "🐾 THÚ CƯNG",
            "lootbox": "🎁 HỘP QUÀ",
            "consumable": "🍪 VẬT PHẨM TIÊU HAO",
            "collectible": "💎 VẬT PHẨM SƯU TẦM"
        }
        
        embed = discord.Embed(
            title=f"🏪 {category_names.get(category, category.upper())}",
            description=f"Dùng `+buy <item_id>` để mua\nDùng `+about {category}` để xem chi tiết",
            color=discord.Color.gold()
        )
        
        for item_id, item in sorted(items.items(), key=lambda x: x[1]["price"]):
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"**ID:** `{item_id}`\n💰 **{item['price']:,}** coins",
                inline=True
            )
        
        embed.set_footer(text="Mua: +buy <item_id> • Xem túi đồ: +inventory")
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="buy", help="Mua vật phẩm 🛒")
    async def buy_cmd(ctx: commands.Context, item_id: str = None, quantity: int = 1) -> None:
        if not item_id:
            return await ctx.reply("Bạn muốn mua gì? Dùng `+shop` để xem danh sách nha~", mention_author=False)
        
        if quantity < 1:
            return await ctx.reply("Số lượng phải lớn hơn 0!", mention_author=False)
        
        item = shop_system.get_item_info(item_id)
        if not item:
            return await ctx.reply(f"❌ Không tìm thấy vật phẩm `{item_id}`!", mention_author=False)
        
        total_cost = item["price"] * quantity
        
        # Check balance
        stats = economy.get_user(str(ctx.author.id))
        if stats["balance"] < total_cost:
            return await ctx.reply(f"❌ Bạn không đủ tiền! Cần **{total_cost:,}** coins nhưng chỉ có **{stats['balance']:,}** coins.", mention_author=False)
        
        # Deduct money
        economy.remove_money(str(ctx.author.id), total_cost)
        
        # Add item
        shop_system.add_item(str(ctx.author.id), item_id, quantity)
        
        embed = discord.Embed(
            title="✅ MUA THÀNH CÔNG!",
            description=f"Bạn đã mua **{quantity}x** {item['emoji']} **{item['name']}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Tổng chi phí", value=f"💰 **{total_cost:,}** coins", inline=True)
        embed.add_field(name="Số dư còn lại", value=f"💵 **{stats['balance'] - total_cost:,}** coins", inline=True)
        embed.set_footer(text="Dùng +inventory để xem túi đồ")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="inventory", aliases=["inv", "bag"], help="Xem túi đồ 🎒")
    async def inventory_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        target = member or ctx.author
        inventory = shop_system.get_user_inventory(str(target.id))
        
        items = inventory.get("items", {})
        equipped = inventory.get("equipped", {})
        
        if not items and not equipped:
            if target.id == ctx.author.id:
                return await ctx.reply("Túi đồ của bạn trống! Dùng `+shop` để mua vật phẩm nha~", mention_author=False)
            else:
                return await ctx.reply(f"Túi đồ của {target.mention} trống!", mention_author=False)
        
        embed = discord.Embed(
            title=f"🎒 TÚI ĐỒ - {target.display_name}",
            color=discord.Color.blue()
        )
        
        # Show equipped items
        if equipped:
            equipped_text = []
            for category, item_id in equipped.items():
                item_info = shop_system.get_item_info(item_id)
                if item_info:
                    equipped_text.append(f"{item_info['emoji']} **{item_info['name']}** ({category})")
            
            if equipped_text:
                embed.add_field(
                    name="✨ ĐANG TRANG BỊ",
                    value="\n".join(equipped_text),
                    inline=False
                )
        
        # Show items by category
        categories = {}
        for item_id, quantity in items.items():
            item_info = shop_system.get_item_info(item_id)
            if item_info:
                cat = item_info["category"]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(f"{item_info['emoji']} **{item_info['name']}** x{quantity}")
        
        for category, item_list in categories.items():
            cat_names = {
                "ring": "💍 Nhẫn",
                "pet": "🐾 Thú Cưng",
                "lootbox": "🎁 Hộp Quà",
                "consumable": "🍪 Tiêu Hao",
                "collectible": "💎 Sưu Tầm"
            }
            embed.add_field(
                name=cat_names.get(category, category.upper()),
                value="\n".join(item_list),
                inline=True
            )
        
        # Show total value
        total_value = shop_system.get_inventory_value(str(target.id))
        embed.set_footer(text=f"Tổng giá trị: {total_value:,} coins • Dùng +equip <item_id> để trang bị")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="equip", help="Trang bị vật phẩm ⚔️")
    async def equip_cmd(ctx: commands.Context, item_id: str = None) -> None:
        if not item_id:
            return await ctx.reply("Bạn muốn trang bị gì? Dùng `+inventory` để xem túi đồ nha~", mention_author=False)
        
        success, message = shop_system.equip_item(str(ctx.author.id), item_id)
        await ctx.reply(message, mention_author=False)
    
    @bot.command(name="unequip", help="Gỡ trang bị 🔓")
    async def unequip_cmd(ctx: commands.Context, category: str = None) -> None:
        if not category:
            return await ctx.reply("Bạn muốn gỡ gì? Dùng `+unequip ring` hoặc `+unequip pet`", mention_author=False)
        
        category = category.lower()
        if category not in ["ring", "pet"]:
            return await ctx.reply("❌ Category không hợp lệ! Chỉ có `ring` hoặc `pet`.", mention_author=False)
        
        success, message = shop_system.unequip_item(str(ctx.author.id), category)
        await ctx.reply(message, mention_author=False)
    
    @bot.command(name="use", help="Sử dụng vật phẩm 🎯")
    async def use_cmd(ctx: commands.Context, item_id: str = None) -> None:
        if not item_id:
            return await ctx.reply("Bạn muốn dùng gì? Dùng `+inventory` để xem túi đồ nha~", mention_author=False)
        
        item = shop_system.get_item_info(item_id)
        if not item:
            return await ctx.reply(f"❌ Không tìm thấy vật phẩm `{item_id}`!", mention_author=False)
        
        # Check if it's a lootbox
        if item["category"] == "lootbox":
            success, message, rewards = shop_system.open_lootbox(str(ctx.author.id), item_id)
            if not success:
                return await ctx.reply(message, mention_author=False)
            
            # Add coins to user
            coins_reward = next((r["amount"] for r in rewards if r["type"] == "coins"), 0)
            if coins_reward > 0:
                economy.add_money(str(ctx.author.id), coins_reward)
            
            # Create rewards embed
            embed = discord.Embed(
                title="🎁 MỞ HỘP QUÀ!",
                description=f"Bạn đã mở {item['emoji']} **{item['name']}**!",
                color=discord.Color.gold()
            )
            
            rewards_text = []
            for reward in rewards:
                if reward["type"] == "coins":
                    rewards_text.append(f"💰 **{reward['amount']:,}** coins")
                else:
                    rewards_text.append(f"{reward['emoji']} **{reward['name']}**")
            
            embed.add_field(name="🎉 Phần thưởng", value="\n".join(rewards_text), inline=False)
            embed.set_footer(text="Chúc mừng! Dùng +inventory để xem túi đồ")
            
            await ctx.reply(embed=embed, mention_author=False)
        else:
            # Use consumable or other items
            success, message, effect_data = shop_system.use_item(str(ctx.author.id), item_id)
            await ctx.reply(message, mention_author=False)
    
    @bot.command(name="sell", help="Bán vật phẩm 💵")
    async def sell_cmd(ctx: commands.Context, item_id: str = None, quantity: int = 1) -> None:
        if not item_id:
            return await ctx.reply("Bạn muốn bán gì? Dùng `+inventory` để xem túi đồ nha~", mention_author=False)
        
        if quantity < 1:
            return await ctx.reply("Số lượng phải lớn hơn 0!", mention_author=False)
        
        item = shop_system.get_item_info(item_id)
        if not item:
            return await ctx.reply(f"❌ Không tìm thấy vật phẩm `{item_id}`!", mention_author=False)
        
        # Check if user has item
        if not shop_system.has_item(str(ctx.author.id), item_id, quantity):
            return await ctx.reply(f"❌ Bạn không có đủ **{quantity}x** {item['emoji']} **{item['name']}**!", mention_author=False)
        
        # Sell for 50% of original price
        sell_price = int(item["price"] * 0.5 * quantity)
        
        # Remove item and add money
        shop_system.remove_item(str(ctx.author.id), item_id, quantity)
        economy.add_money(str(ctx.author.id), sell_price)
        
        embed = discord.Embed(
            title="✅ BÁN THÀNH CÔNG!",
            description=f"Bạn đã bán **{quantity}x** {item['emoji']} **{item['name']}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Nhận được", value=f"💰 **{sell_price:,}** coins", inline=True)
        embed.set_footer(text="Giá bán = 50% giá mua")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="gift", help="Tặng quà cho ai đó 🎁")
    async def gift_cmd(ctx: commands.Context, member: discord.Member = None, item_id: str = None) -> None:
        if not member or not item_id:
            return await ctx.reply("Dùng: `+gift @user <item_id>`", mention_author=False)
        
        if member.bot:
            return await ctx.reply("Không thể tặng quà cho bot!", mention_author=False)
        
        if member.id == ctx.author.id:
            return await ctx.reply("Không thể tặng quà cho chính mình!", mention_author=False)
        
        item = shop_system.get_item_info(item_id)
        if not item:
            return await ctx.reply(f"❌ Không tìm thấy vật phẩm `{item_id}`!", mention_author=False)
        
        if not item.get("tradeable", False):
            return await ctx.reply(f"❌ {item['emoji']} **{item['name']}** không thể trao đổi!", mention_author=False)
        
        # Check if user has item
        if not shop_system.has_item(str(ctx.author.id), item_id):
            return await ctx.reply(f"❌ Bạn không có {item['emoji']} **{item['name']}**!", mention_author=False)
        
        # Transfer item
        shop_system.remove_item(str(ctx.author.id), item_id)
        shop_system.add_item(str(member.id), item_id)
        
        embed = discord.Embed(
            title="🎁 TẶNG QUÀ THÀNH CÔNG!",
            description=f"{ctx.author.mention} đã tặng {member.mention}\n{item['emoji']} **{item['name']}**!",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.set_footer(text="Thật là tử tế! 💕")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    # ==================== INTERACTION COMMANDS ====================
    
    async def check_interaction_target(ctx, member):
        """Check if interaction target is valid"""
        if not member:
            await ctx.reply("Bạn muốn tương tác với ai? Tag người đó nha~ 💕", mention_author=False)
            return False
        if member.id == ctx.author.id:
            await ctx.reply("Tự tương tác với mình à? 😅", mention_author=False)
            return False
        if member.bot:
            await ctx.reply("Không thể dùng lệnh này với bot nha~ 😅", mention_author=False)
            return False
        return True
    
    async def send_interaction_embed(ctx, action: str, member: discord.Member, color: discord.Color):
        """Send interaction embed with cache-busting"""
        import time
        gif_url, message = interaction_system.get_interaction(action, ctx.author.mention, member.mention)
        timestamp = int(time.time())
        
        embed = discord.Embed(
            description=message,
            color=color,
            timestamp=datetime.now()
        )
        embed.set_image(url=f"{gif_url}?t={timestamp}")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="kiss", help="Hôn ai đó 💋")
    async def kiss_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "kiss", member, discord.Color.from_rgb(255, 182, 193))
    
    @bot.command(name="hug", help="Ôm ai đó 🤗")
    async def hug_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "hug", member, discord.Color.from_rgb(255, 192, 203))
    
    @bot.command(name="pat", help="Vỗ đầu ai đó 👋")
    async def pat_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "pat", member, discord.Color.from_rgb(255, 223, 186))
    
    @bot.command(name="slap", help="Tát ai đó 👋")
    async def slap_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "slap", member, discord.Color.from_rgb(255, 99, 71))
    
    @bot.command(name="cuddle", help="Âu yếm ai đó 🥰")
    async def cuddle_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "cuddle", member, discord.Color.from_rgb(255, 182, 193))
    
    @bot.command(name="poke", help="Chọc ai đó 👉")
    async def poke_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "poke", member, discord.Color.from_rgb(135, 206, 250))
    
    @bot.command(name="lick", help="Liếm ai đó 👅")
    async def lick_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "lick", member, discord.Color.from_rgb(255, 105, 180))
    
    @bot.command(name="bite", help="Cắn ai đó 🦷")
    async def bite_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "bite", member, discord.Color.from_rgb(220, 20, 60))
    
    @bot.command(name="punch", help="Đấm ai đó 👊")
    async def punch_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "punch", member, discord.Color.from_rgb(178, 34, 34))
    
    @bot.command(name="tickle", help="Cù ai đó 🤭")
    async def tickle_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "tickle", member, discord.Color.from_rgb(255, 215, 0))
    
    @bot.command(name="highfive", help="Vỗ tay với ai đó ✋")
    async def highfive_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "highfive", member, discord.Color.from_rgb(50, 205, 50))
    
    @bot.command(name="boop", help="Boop mũi ai đó 👃")
    async def boop_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "boop", member, discord.Color.from_rgb(255, 192, 203))
    
    @bot.command(name="wave", help="Vẫy tay với ai đó 👋")
    async def wave_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "wave", member, discord.Color.from_rgb(135, 206, 235))
    
    @bot.command(name="nom", help="Nom nom ai đó 😋")
    async def nom_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "nom", member, discord.Color.from_rgb(255, 140, 0))
    
    @bot.command(name="stare", help="Nhìn chằm chằm ai đó 👀")
    async def stare_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not await check_interaction_target(ctx, member):
            return
        await send_interaction_embed(ctx, "stare", member, discord.Color.from_rgb(138, 43, 226))
    
    # ==================== MARRIAGE COMMANDS ====================
    
    # Temporary storage for marriage proposals
    marriage_proposals = {}
    
    @bot.command(name="marry", help="Cầu hôn ai đó 💍")
    async def marry_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if not member:
            return await ctx.reply("Bạn muốn cầu hôn ai? Tag người đó nha~ 💕", mention_author=False)
        
        if member.bot:
            return await ctx.reply("Không thể cầu hôn bot nha~ 😅", mention_author=False)
        
        if member.id == ctx.author.id:
            return await ctx.reply("Không thể cầu hôn chính mình! 😂", mention_author=False)
        
        # Check if proposer has a ring equipped
        equipped_ring = shop_system.get_equipped_item(str(ctx.author.id), "ring")
        if not equipped_ring:
            return await ctx.reply("Bạn cần trang bị nhẫn trước khi cầu hôn! Dùng `+shop ring` để mua nhẫn nha~ 💍", mention_author=False)
        
        # Check if can propose
        can_propose, message = marriage_system.propose(str(ctx.author.id), str(member.id))
        if not can_propose:
            return await ctx.reply(message, mention_author=False)
        
        # Store proposal
        marriage_proposals[member.id] = {
            "proposer_id": ctx.author.id,
            "ring_id": equipped_ring,
            "timestamp": datetime.now()
        }
        
        # Create proposal embed
        ring_info = shop_system.get_item_info(equipped_ring)
        embed = discord.Embed(
            title="💍 CẦU HÔN 💍",
            description=f"{ctx.author.mention} đang cầu hôn {member.mention}!\n\n{ring_info['emoji']} **{ring_info['name']}**\n\n{member.mention}, bạn có đồng ý kết hôn không?",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.set_footer(text="Dùng +accept để đồng ý hoặc +reject để từ chối • Có 5 phút để quyết định")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="accept", help="Đồng ý lời cầu hôn ✅")
    async def accept_proposal_cmd(ctx: commands.Context) -> None:
        if ctx.author.id not in marriage_proposals:
            return await ctx.reply("Không có ai cầu hôn bạn! 💔", mention_author=False)
        
        proposal = marriage_proposals[ctx.author.id]
        
        # Check if proposal expired (5 minutes)
        if (datetime.now() - proposal["timestamp"]).total_seconds() > 300:
            del marriage_proposals[ctx.author.id]
            return await ctx.reply("⏰ Lời cầu hôn đã hết hạn!", mention_author=False)
        
        proposer_id = proposal["proposer_id"]
        ring_id = proposal["ring_id"]
        
        # Accept proposal
        success, result = marriage_system.marry(str(proposer_id), str(ctx.author.id), ring_id)
        if success:
            # Remove ring from proposer's equipped
            shop_system.unequip_item(str(proposer_id), "ring")
            
            proposer = await bot.fetch_user(proposer_id)
            
            embed = discord.Embed(
                title="🎉 CHÚC MỪNG! 🎉",
                description=f"{proposer.mention} ❤️ {ctx.author.mention}\n\n{result}\n\nHai bạn giờ đã là vợ chồng! 💑",
                color=discord.Color.from_rgb(255, 105, 180)
            )
            embed.set_footer(text="Dùng +marriage để xem thông tin hôn nhân")
            await ctx.send(embed=embed)
            
            # Remove proposal
            del marriage_proposals[ctx.author.id]
        else:
            await ctx.reply(result, mention_author=False)
    
    @bot.command(name="reject", help="Từ chối lời cầu hôn ❌")
    async def reject_proposal_cmd(ctx: commands.Context) -> None:
        if ctx.author.id not in marriage_proposals:
            return await ctx.reply("Không có ai cầu hôn bạn! 💔", mention_author=False)
        
        proposal = marriage_proposals[ctx.author.id]
        proposer_id = proposal["proposer_id"]
        
        proposer = await bot.fetch_user(proposer_id)
        
        await ctx.reply(f"💔 {ctx.author.mention} đã từ chối lời cầu hôn của {proposer.mention}...", mention_author=False)
        
        # Remove proposal
        del marriage_proposals[ctx.author.id]
    
    @bot.command(name="divorce", help="Ly hôn 💔")
    async def divorce_cmd(ctx: commands.Context) -> None:
        if not marriage_system.is_married(str(ctx.author.id)):
            return await ctx.reply("Bạn chưa kết hôn!", mention_author=False)
        
        partner_id = marriage_system.get_partner(str(ctx.author.id))
        partner = await bot.fetch_user(int(partner_id))
        
        embed = discord.Embed(
            title="💔 LY HÔN",
            description=f"Bạn có chắc muốn ly hôn với {partner.mention}?\n\nĐây là quyết định nghiêm trọng!",
            color=discord.Color.red()
        )
        embed.set_footer(text="React ✅ để xác nhận, ❌ để hủy • Có 30 giây")
        
        msg = await ctx.reply(embed=embed, mention_author=False)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        
        def check(reaction, user):
            return user.id == ctx.author.id and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
        
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                success, result = marriage_system.divorce(str(ctx.author.id))
                await ctx.reply(result, mention_author=False)
            else:
                await ctx.reply("Đã hủy ly hôn.", mention_author=False)
        
        except asyncio.TimeoutError:
            await ctx.reply("⏰ Hết thời gian! Đã hủy ly hôn.", mention_author=False)
    
    @bot.command(name="marriage", aliases=["married", "spouse"], help="Xem thông tin hôn nhân 💑")
    async def marriage_info_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        target = member or ctx.author
        
        if not marriage_system.is_married(str(target.id)):
            if target.id == ctx.author.id:
                return await ctx.reply("Bạn chưa kết hôn! Dùng `+marry @user` để cầu hôn nha~ 💍", mention_author=False)
            else:
                return await ctx.reply(f"{target.mention} chưa kết hôn!", mention_author=False)
        
        marriage_info = marriage_system.get_marriage_info(str(target.id))
        partner_id = marriage_info["partner"]
        partner = await bot.fetch_user(int(partner_id))
        
        duration = marriage_system.get_marriage_duration(str(target.id))
        love_points = marriage_info.get("love_points", 0)
        ring_id = marriage_info.get("ring")
        
        ring_info = shop_system.get_item_info(ring_id) if ring_id else None
        ring_text = f"{ring_info['emoji']} {ring_info['name']}" if ring_info else "Không có nhẫn"
        
        embed = discord.Embed(
            title="💑 THÔNG TIN HÔN NHÂN",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.add_field(name="Vợ/Chồng", value=f"{target.mention} ❤️ {partner.mention}", inline=False)
        embed.add_field(name="Nhẫn Cưới", value=ring_text, inline=True)
        embed.add_field(name="Thời Gian", value=duration, inline=True)
        embed.add_field(name="Điểm Tình Yêu", value=f"💕 {love_points:,}", inline=True)
        embed.set_footer(text="Dùng +divorce để ly hôn")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="about", help="Xem thông tin chi tiết về vật phẩm 📖")
    async def about_cmd(ctx: commands.Context, category: str = None) -> None:
        if not category:
            # Show available categories
            embed = discord.Embed(
                title="📖 ABOUT - THÔNG TIN VẬT PHẨM",
                description="Xem thông tin chi tiết về các loại vật phẩm trong shop!\n\n**Cách dùng:** `+about <category>`",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📂 Categories",
                value="• `ring` - Nhẫn 💍\n• `pet` - Thú cưng 🐾\n• `lootbox` - Hộp quà 🎁\n• `consumable` - Vật phẩm tiêu hao 🍪\n• `collectible` - Vật phẩm sưu tầm 💎",
                inline=False
            )
            embed.set_footer(text="Ví dụ: +about ring")
            return await ctx.reply(embed=embed, mention_author=False)
        
        category = category.lower()
        
        # Get items by category
        items = shop_system.get_shop_items(category)
        
        if not items:
            return await ctx.reply(f"❌ Không tìm thấy category `{category}`!\nDùng `+about` để xem danh sách categories.", mention_author=False)
        
        # Create detailed embed based on category
        if category == "ring":
            embed = discord.Embed(
                title="💍 NHẪN - WEDDING RINGS",
                description="**⚠️ LƯU Ý QUAN TRỌNG:**\nNhẫn chỉ có hiệu lực khi bạn **ĐÃ KẾT HÔN** (dùng `+marry`)!\nKhi chưa kết hôn, nhẫn chỉ là vật phẩm trang trí.\n\n**Buff khi đã kết hôn:**",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            
            for item_id, item in sorted(items.items(), key=lambda x: x[1]["price"]):
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"💰 **Giá:** {item['price']:,} coins\n📝 {item['description']}\n✨ **Buff:** {item['effect']}\n━━━━━━━━━━━━━━",
                    inline=False
                )
            
            embed.set_footer(text="Mua nhẫn: +buy <item_id> • Trang bị: +equip <item_id> • Cầu hôn: +marry @user")
        
        elif category == "pet":
            embed = discord.Embed(
                title="🐾 THÚ CƯNG - PETS",
                description="Thú cưng giúp bạn tăng XP mỗi ngày!\n**Buff hoạt động ngay khi trang bị.**",
                color=discord.Color.from_rgb(100, 200, 255)
            )
            
            for item_id, item in sorted(items.items(), key=lambda x: x[1]["price"]):
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"💰 **Giá:** {item['price']:,} coins\n📝 {item['description']}\n✨ **Buff:** {item['effect']}\n━━━━━━━━━━━━━━",
                    inline=False
                )
            
            embed.set_footer(text="Mua pet: +buy <item_id> • Trang bị: +equip <item_id>")
        
        elif category == "lootbox":
            embed = discord.Embed(
                title="🎁 HỘP QUÀ - LOOTBOXES",
                description="Mở hộp quà để nhận vật phẩm ngẫu nhiên và coins!",
                color=discord.Color.from_rgb(255, 215, 0)
            )
            
            for item_id, item in sorted(items.items(), key=lambda x: x[1]["price"]):
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"💰 **Giá:** {item['price']:,} coins\n📝 {item['description']}\n✨ {item['effect']}\n━━━━━━━━━━━━━━",
                    inline=False
                )
            
            embed.set_footer(text="Mua hộp: +buy <item_id> • Mở hộp: +use <item_id>")
        
        elif category == "consumable":
            embed = discord.Embed(
                title="🍪 VẬT PHẨM TIÊU HAO - CONSUMABLES",
                description="Vật phẩm dùng 1 lần để tăng tỷ lệ thắng casino!",
                color=discord.Color.from_rgb(255, 140, 0)
            )
            
            for item_id, item in sorted(items.items(), key=lambda x: x[1]["price"]):
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"💰 **Giá:** {item['price']:,} coins\n📝 {item['description']}\n✨ **Hiệu ứng:** {item['effect']}\n━━━━━━━━━━━━━━",
                    inline=False
                )
            
            embed.set_footer(text="Mua: +buy <item_id> • Dùng: +use <item_id>")
        
        elif category == "collectible":
            embed = discord.Embed(
                title="💎 VẬT PHẨM SƯU TẦM - COLLECTIBLES",
                description="Vật phẩm quý hiếm để khoe với bạn bè!",
                color=discord.Color.from_rgb(138, 43, 226)
            )
            
            for item_id, item in sorted(items.items(), key=lambda x: x[1]["price"]):
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"💰 **Giá:** {item['price']:,} coins\n📝 {item['description']}\n✨ {item['effect']}\n━━━━━━━━━━━━━━",
                    inline=False
                )
            
            embed.set_footer(text="Mua: +buy <item_id> • Xem: +inventory")
        
        else:
            return await ctx.reply(f"❌ Category `{category}` chưa có thông tin chi tiết!", mention_author=False)
        
        await ctx.reply(embed=embed, mention_author=False)

    @bot.command(name="avatar", aliases=["av", "pfp"], help="Xem avatar của user")
    async def avatar_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        member = member or ctx.author
        embed = discord.Embed(
            title=f"Avatar của {member.display_name}",
            color=member.color
        )
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.reply(embed=embed, mention_author=False)

    @bot.command(name="serverinfo", aliases=["si", "server"], help="Thông tin về server")
    async def serverinfo_cmd(ctx: commands.Context) -> None:
        if not ctx.guild:
            return await ctx.reply("Lệnh này chỉ dùng trong server nha~", mention_author=False)
        
        guild = ctx.guild
        embed = discord.Embed(
            title=f"📊 {guild.name}",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
        embed.add_field(name="📅 Created", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
        embed.add_field(name="💬 Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="😀 Emojis", value=len(guild.emojis), inline=True)
        embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="🚀 Boost Level", value=guild.premium_tier, inline=True)
        embed.add_field(name="💎 Boosts", value=guild.premium_subscription_count or 0, inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)

    @bot.command(name="userinfo", aliases=["ui", "whois"], help="Thông tin về user")
    async def userinfo_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="🏷️ Username", value=f"{member.name}", inline=True)
        embed.add_field(name="🆔 User ID", value=member.id, inline=True)
        embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="📅 Account Created", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
        
        if ctx.guild and member in ctx.guild.members:
            embed.add_field(name="📥 Joined Server", value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "Unknown", inline=True)
            roles = [role.mention for role in member.roles if role.name != "@everyone"]
            if roles:
                embed.add_field(name=f"🎭 Roles [{len(roles)}]", value=" ".join(roles[:10]), inline=False)
        
        await ctx.reply(embed=embed, mention_author=False)

    # ==================== ECONOMY COMMANDS ====================
    
    @bot.command(name="balance", aliases=["bal", "money"], help="Xem số tiền của bạn")
    async def balance_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        member = member or ctx.author
        user_id = str(member.id)
        
        is_infinity = economy.is_infinity(user_id)
        
        if is_infinity:
            balance_str = "**∞**"
            bank_str = "**∞**"
            total_str = "**∞**"
        else:
            balance = economy.get_balance(user_id)
            bank = economy.get_bank(user_id)
            total = balance + bank
            balance_str = f"**{balance:,}** coins"
            bank_str = f"**{bank:,}** coins"
            total_str = f"**{total:,}** coins"
        
        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Balance",
            color=discord.Color.gold()
        )
        embed.add_field(name="💵 Wallet", value=balance_str, inline=True)
        embed.add_field(name="🏦 Bank", value=bank_str, inline=True)
        embed.add_field(name="💎 Total", value=total_str, inline=True)
        
        if is_infinity:
            embed.set_footer(text="♾️ Infinity Mode Active")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="daily", help="Nhận phần thưởng hàng ngày")
    async def daily_cmd(ctx: commands.Context) -> None:
        user_id = str(ctx.author.id)
        
        if not economy.can_daily(user_id):
            user = economy.get_user(user_id)
            last_daily = datetime.fromisoformat(user["last_daily"])
            next_daily = last_daily + timedelta(hours=24)
            time_left = next_daily - datetime.now()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            await ctx.reply(f"⏰ Bạn đã nhận daily rồi! Quay lại sau **{hours}h {minutes}m** nha~", mention_author=False)
            return
        
        result = economy.claim_daily(user_id)
        
        embed = discord.Embed(
            title="🎁 Daily Reward",
            color=discord.Color.gold()
        )
        embed.add_field(name="💰 Coins", value=f"+{result['amount']:,}", inline=True)
        embed.add_field(name="⭐ XP", value=f"+{result['xp_gained']}", inline=True)
        embed.add_field(name="📊 Level", value=f"{result['level']}", inline=True)
        embed.add_field(name="🔥 Streak", value=f"{result['streak']} days", inline=True)
        embed.add_field(name="📈 Streak Bonus", value=f"+{result['streak_bonus']:.1f}%", inline=True)
        embed.add_field(name="🎯 Level Bonus", value=f"+{result['level_bonus']:.1f}%", inline=True)
        
        if result['new_level']:
            embed.add_field(
                name="🎉 Level Up!",
                value=f"Chúc mừng! Bạn đã lên **Level {result['new_level']}**!",
                inline=False
            )
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="deposit", aliases=["dep"], help="Gửi tiền vào ngân hàng")
    async def deposit_cmd(ctx: commands.Context, amount: str) -> None:
        user_id = str(ctx.author.id)
        
        if amount.lower() == "all":
            amount = economy.get_balance(user_id)
        else:
            try:
                amount = int(amount)
            except ValueError:
                return await ctx.reply("Số tiền không hợp lệ! Dùng số hoặc 'all' nha~", mention_author=False)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        if economy.deposit(user_id, amount):
            await ctx.reply(f"🏦 Đã gửi **{amount:,}** coins vào ngân hàng!", mention_author=False)
        else:
            await ctx.reply("Bạn không đủ tiền trong ví nha~", mention_author=False)
    
    @bot.command(name="withdraw", aliases=["with"], help="Rút tiền từ ngân hàng")
    async def withdraw_cmd(ctx: commands.Context, amount: str) -> None:
        user_id = str(ctx.author.id)
        
        if amount.lower() == "all":
            amount = economy.get_bank(user_id)
        else:
            try:
                amount = int(amount)
            except ValueError:
                return await ctx.reply("Số tiền không hợp lệ! Dùng số hoặc 'all' nha~", mention_author=False)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        if economy.withdraw(user_id, amount):
            await ctx.reply(f"💵 Đã rút **{amount:,}** coins từ ngân hàng!", mention_author=False)
        else:
            await ctx.reply("Bạn không đủ tiền trong ngân hàng nha~", mention_author=False)
    
    @bot.command(name="give", aliases=["pay"], help="Chuyển tiền cho người khác (owner: unlimited)")
    async def give_cmd(ctx: commands.Context, member: discord.Member, amount: int) -> None:
        if member.bot:
            return await ctx.reply("Không thể chuyển tiền cho bot nha~", mention_author=False)
        
        if member.id == ctx.author.id:
            return await ctx.reply("Không thể tự chuyển tiền cho mình nha~", mention_author=False)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        from_user = str(ctx.author.id)
        to_user = str(member.id)
        
        # Owner can give unlimited money
        is_owner = ctx.author.id in OWNER_IDS
        if is_owner:
            economy.add_money(to_user, amount)
            await ctx.reply(f"💸 [Owner] Đã tặng **{amount:,}** coins cho {member.mention}!", mention_author=False)
        elif economy.transfer(from_user, to_user, amount):
            await ctx.reply(f"💸 Đã chuyển **{amount:,}** coins cho {member.mention}!", mention_author=False)
        else:
            await ctx.reply("Bạn không đủ tiền nha~", mention_author=False)
    
    # ==================== CASINO GAMES ====================
    
    @bot.command(name="cf", aliases=["coinflip_bet"], help="Tung đồng xu cá cược (cf <heads/tails> <số tiền>)")
    async def coinflip_bet(ctx: commands.Context, choice: str, amount: int) -> None:
        user_id = str(ctx.author.id)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        if amount > economy.get_balance(user_id):
            return await ctx.reply("Bạn không đủ tiền nha~", mention_author=False)
        
        choice = choice.lower()
        if choice not in ["heads", "tails", "ngửa", "sấp", "h", "t"]:
            return await ctx.reply("Chọn heads/tails (hoặc ngửa/sấp) nha~", mention_author=False)
        
        # Normalize choice
        if choice in ["heads", "ngửa", "h"]:
            user_choice = "heads"
        else:
            user_choice = "tails"
        
        import random
        result = random.choice(["heads", "tails"])
        
        if result == user_choice:
            economy.add_money(user_id, amount)
            economy.record_win(user_id)
            await ctx.reply(f"🪙 Kết quả: **{'Ngửa' if result == 'heads' else 'Sấp'}**\n🎉 Bạn thắng **{amount:,}** coins!", mention_author=False)
        else:
            economy.remove_money(user_id, amount)
            economy.record_loss(user_id)
            await ctx.reply(f"🪙 Kết quả: **{'Ngửa' if result == 'heads' else 'Sấp'}**\n😔 Bạn thua **{amount:,}** coins!", mention_author=False)
    
    @bot.command(name="slots", aliases=["slot"], help="Chơi slot machine (slots <số tiền>)")
    async def slots_cmd(ctx: commands.Context, amount: int) -> None:
        user_id = str(ctx.author.id)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        if amount > economy.get_balance(user_id):
            return await ctx.reply("Bạn không đủ tiền nha~", mention_author=False)
        
        import random
        emojis = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
        
        slot1 = random.choice(emojis)
        slot2 = random.choice(emojis)
        slot3 = random.choice(emojis)
        
        # Calculate winnings
        if slot1 == slot2 == slot3:
            if slot1 == "💎":
                multiplier = 10
            elif slot1 == "7️⃣":
                multiplier = 7
            else:
                multiplier = 5
            winnings = amount * multiplier
            economy.add_money(user_id, winnings)
            economy.record_win(user_id)
            await ctx.reply(f"🎰 | {slot1} {slot2} {slot3} |\n🎉 JACKPOT! Bạn thắng **{winnings:,}** coins! (x{multiplier})", mention_author=False)
        elif slot1 == slot2 or slot2 == slot3 or slot1 == slot3:
            winnings = amount * 2
            economy.add_money(user_id, winnings - amount)
            economy.record_win(user_id)
            await ctx.reply(f"🎰 | {slot1} {slot2} {slot3} |\n✨ Bạn thắng **{winnings:,}** coins! (x2)", mention_author=False)
        else:
            economy.remove_money(user_id, amount)
            economy.record_loss(user_id)
            await ctx.reply(f"🎰 | {slot1} {slot2} {slot3} |\n😔 Bạn thua **{amount:,}** coins!", mention_author=False)
    
    @bot.command(name="bj", aliases=["blackjack"], help="Chơi blackjack (bj <số tiền>)")
    async def blackjack_cmd(ctx: commands.Context, amount: int) -> None:
        user_id = str(ctx.author.id)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        if amount > economy.get_balance(user_id):
            return await ctx.reply("Bạn không đủ tiền nha~", mention_author=False)
        
        import random
        
        def card_value(card):
            if card in ['J', 'Q', 'K']:
                return 10
            elif card == 'A':
                return 11
            else:
                return int(card)
        
        def hand_value(hand):
            value = sum(card_value(card) for card in hand)
            aces = hand.count('A')
            while value > 21 and aces:
                value -= 10
                aces -= 1
            return value
        
        deck = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4
        random.shuffle(deck)
        
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        
        player_value = hand_value(player_hand)
        dealer_value = hand_value(dealer_hand)
        
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
        embed.add_field(name="Your Hand", value=f"{' '.join(player_hand)} = **{player_value}**", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{dealer_hand[0]} ❓", inline=False)
        
        if player_value == 21:
            winnings = int(amount * 2.5)
            economy.add_money(user_id, winnings)
            economy.record_win(user_id)
            embed.add_field(name="Result", value=f"🎉 BLACKJACK! You win **{winnings:,}** coins!", inline=False)
            return await ctx.reply(embed=embed, mention_author=False)
        
        msg = await ctx.reply(embed=embed, mention_author=False)
        
        # Simple AI dealer logic
        while dealer_value < 17:
            dealer_hand.append(deck.pop())
            dealer_value = hand_value(dealer_hand)
        
        # Reveal dealer's hand
        embed.set_field_at(1, name="Dealer's Hand", value=f"{' '.join(dealer_hand)} = **{dealer_value}**", inline=False)
        
        if dealer_value > 21:
            winnings = amount * 2
            economy.add_money(user_id, winnings)
            economy.record_win(user_id)
            embed.add_field(name="Result", value=f"🎉 Dealer busts! You win **{winnings:,}** coins!", inline=False)
        elif player_value > dealer_value:
            winnings = amount * 2
            economy.add_money(user_id, winnings)
            economy.record_win(user_id)
            embed.add_field(name="Result", value=f"🎉 You win **{winnings:,}** coins!", inline=False)
        elif player_value == dealer_value:
            embed.add_field(name="Result", value=f"🤝 Push! Your **{amount:,}** coins returned.", inline=False)
        else:
            economy.remove_money(user_id, amount)
            economy.record_loss(user_id)
            embed.add_field(name="Result", value=f"😔 Dealer wins! You lose **{amount:,}** coins!", inline=False)
        
        await msg.edit(embed=embed)
    
    @bot.command(name="tx", aliases=["taixiu", "gamble"], help="Cá cược tài xỉu (tx <số tiền>)")
    async def tx_cmd(ctx: commands.Context, amount: int) -> None:
        user_id = str(ctx.author.id)
        
        if amount <= 0:
            return await ctx.reply("Số tiền phải lớn hơn 0 nha~", mention_author=False)
        
        if amount > economy.get_balance(user_id):
            return await ctx.reply("Bạn không đủ tiền nha~", mention_author=False)
        
        import random
        
        # Roll 3 dice
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        dice3 = random.randint(1, 6)
        total = dice1 + dice2 + dice3
        
        result = "TÀI" if total >= 11 else "XỈU"
        
        # 50/50 chance
        win = random.choice([True, False])
        
        embed = discord.Embed(title="🎲 Tài Xỉu", color=discord.Color.red())
        embed.add_field(name="Dice Roll", value=f"🎲 {dice1} | 🎲 {dice2} | 🎲 {dice3}", inline=False)
        embed.add_field(name="Total", value=f"**{total}** ({result})", inline=False)
        
        if win:
            winnings = amount * 2
            economy.add_money(user_id, winnings)
            economy.record_win(user_id)
            embed.add_field(name="Result", value=f"🎉 You win **{winnings:,}** coins!", inline=False)
            embed.color = discord.Color.green()
        else:
            economy.remove_money(user_id, amount)
            economy.record_loss(user_id)
            embed.add_field(name="Result", value=f"😔 You lose **{amount:,}** coins!", inline=False)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="stats", aliases=["profile"], help="Xem thống kê của bạn")
    async def stats_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        member = member or ctx.author
        user_id = str(member.id)
        stats = economy.get_stats(user_id)
        
        total_games = stats["wins"] + stats["losses"]
        win_rate = (stats["wins"] / total_games * 100) if total_games > 0 else 0
        
        is_infinity = economy.is_infinity(user_id)
        level = stats.get("level", 1)
        xp = stats.get("xp", 0)
        xp_needed = economy.get_xp_for_level(level)
        streak = stats.get("daily_streak", 0)
        
        embed = discord.Embed(
            title=f"📊 {member.display_name}'s Profile",
            color=discord.Color.gold() if is_infinity else discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Level & XP
        if is_infinity:
            embed.add_field(name="📊 Level", value="**∞**", inline=True)
            embed.add_field(name="⭐ XP", value="**∞**", inline=True)
        else:
            embed.add_field(name="📊 Level", value=f"**{level}**", inline=True)
            embed.add_field(name="⭐ XP", value=f"**{xp}/{xp_needed}**", inline=True)
        embed.add_field(name="🔥 Daily Streak", value=f"**{streak}** days", inline=True)
        
        # Economy
        if is_infinity:
            embed.add_field(name="💰 Total Wealth", value="**∞** coins", inline=True)
        else:
            embed.add_field(name="💰 Total Wealth", value=f"**{stats['balance'] + stats['bank']:,}** coins", inline=True)
        embed.add_field(name="📈 Total Earned", value=f"**{stats['total_earned']:,}** coins", inline=True)
        embed.add_field(name="📉 Total Spent", value=f"**{stats['total_spent']:,}** coins", inline=True)
        
        # Casino Stats
        embed.add_field(name="🎮 Games Played", value=f"**{total_games}**", inline=True)
        embed.add_field(name="✅ Wins", value=f"**{stats['wins']}**", inline=True)
        embed.add_field(name="❌ Losses", value=f"**{stats['losses']}**", inline=True)
        embed.add_field(name="📊 Win Rate", value=f"**{win_rate:.1f}%**", inline=True)
        
        if is_infinity:
            embed.set_footer(text="♾️ Infinity Mode Active - Unlimited Power!")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @bot.command(name="card", aliases=["profile-card", "pc"], help="Generate profile card image")
    async def card_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        member = member or ctx.author
        user_id = str(member.id)
        stats = economy.get_stats(user_id)
        
        # Get data
        is_infinity = economy.is_infinity(user_id)
        level = stats.get("level", 1)
        xp = stats.get("xp", 0)
        xp_needed = economy.get_xp_for_level(level)
        balance = stats.get("balance", 0)
        bank = stats.get("bank", 0)
        streak = stats.get("daily_streak", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        
        # Get avatar URL
        avatar_url = member.display_avatar.url
        
        # Get equipped items
        equipped_ring_id = shop_system.get_equipped_item(str(member.id), "ring")
        equipped_pet_id = shop_system.get_equipped_item(str(member.id), "pet")
        
        equipped_ring_name = None
        equipped_pet_name = None
        
        if equipped_ring_id:
            ring_info = shop_system.get_item_info(equipped_ring_id)
            equipped_ring_name = ring_info["name"] if ring_info else None
        
        if equipped_pet_id:
            pet_info = shop_system.get_item_info(equipped_pet_id)
            equipped_pet_name = pet_info["name"] if pet_info else None
        
        # Get marriage partner
        partner_name = None
        if marriage_system.is_married(str(member.id)):
            partner_id = marriage_system.get_partner(str(member.id))
            try:
                partner = await bot.fetch_user(int(partner_id))
                partner_name = partner.display_name
            except:
                pass
        
        # Show typing indicator
        async with ctx.typing():
            try:
                # Generate card
                card_image = await profile_card_generator.generate_profile_card(
                    username=member.display_name,
                    avatar_url=avatar_url,
                    level=level,
                    xp=xp,
                    xp_needed=xp_needed,
                    balance=balance,
                    bank=bank,
                    streak=streak,
                    wins=wins,
                    losses=losses,
                    is_infinity=is_infinity,
                    equipped_ring=equipped_ring_name,
                    equipped_pet=equipped_pet_name,
                    partner_name=partner_name
                )
                
                # Send as file
                file = discord.File(card_image, filename=f"{member.name}_profile.png")
                await ctx.reply(file=file, mention_author=False)
                
            except Exception as e:
                await ctx.reply(f"❌ Lỗi khi tạo profile card: {e}", mention_author=False)
                logging.exception("Error generating profile card")
    
    @bot.command(name="setlevel", help="Set level cho user (owner only)")
    async def setlevel_cmd(ctx: commands.Context, member: discord.Member = None, level: int = None) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        
        # If no member specified, set for self
        if member is None:
            member = ctx.author
        
        user_id = str(member.id)
        
        # If no level specified, set infinity
        if level is None:
            economy.set_infinity(user_id, True)
            economy.set_level(user_id, 999999)  # Max level for display
            await ctx.reply(f"✅ Đã set **∞ Level** cho {member.mention}!", mention_author=False)
        else:
            if level < 1:
                await ctx.reply("Level phải >= 1 nha~", mention_author=False)
                return
            
            economy.set_level(user_id, level)
            economy.set_infinity(user_id, False)  # Remove infinity if setting specific level
            await ctx.reply(f"✅ Đã set **Level {level}** cho {member.mention}!", mention_author=False)
    
    @bot.command(name="setinfinity", aliases=["setinf"], help="Set infinity mode (owner only)")
    async def setinfinity_cmd(ctx: commands.Context, member: discord.Member = None) -> None:
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("chỉ có anh yêu của tớ mới được dùng thôi ro!", mention_author=False)
            return
        
        # If no member specified, set for self
        if member is None:
            member = ctx.author
        
        user_id = str(member.id)
        
        # Toggle infinity
        current = economy.is_infinity(user_id)
        economy.set_infinity(user_id, not current)
        
        if not current:
            await ctx.reply(f"✅ Đã bật **∞ Mode** cho {member.mention}! (Unlimited coins & level)", mention_author=False)
        else:
            await ctx.reply(f"✅ Đã tắt **∞ Mode** cho {member.mention}!", mention_author=False)
    
    @bot.command(name="leaderboard", aliases=["lb", "top"], help="Bảng xếp hạng giàu nhất")
    async def leaderboard_cmd(ctx: commands.Context) -> None:
        # Sort users by total wealth
        sorted_users = sorted(
            economy.data.items(),
            key=lambda x: x[1]["balance"] + x[1]["bank"],
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title="🏆 Top 10 Richest Users",
            color=discord.Color.gold()
        )
        
        description = []
        for idx, (user_id, data) in enumerate(sorted_users, 1):
            try:
                user = await bot.fetch_user(int(user_id))
                total = data["balance"] + data["bank"]
                medal = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"**{idx}.**"
                description.append(f"{medal} {user.name} - **{total:,}** coins")
            except:
                continue
        
        embed.description = "\n".join(description) if description else "No data yet!"
        await ctx.reply(embed=embed, mention_author=False)
    
    # ==================== AFK SYSTEM ====================
    
    @bot.command(name="afk", help="Đặt trạng thái AFK")
    async def afk_cmd(ctx: commands.Context, *, reason: str = None) -> None:
        user_id = str(ctx.author.id)
        afk_system.set_afk(user_id, reason)
        
        if reason:
            await ctx.reply(f"💤 Đã đặt AFK: **{reason}**", mention_author=False)
        else:
            await ctx.reply("💤 Đã đặt trạng thái AFK!", mention_author=False)

    # ==================== COMMAND DISABLE SYSTEM (SLASH COMMANDS) ====================
    
    class DisableCommandSelect(discord.ui.Select):
        def __init__(self, channel_id: str):
            self.channel_id = channel_id
            
            # Get all commands grouped by category
            all_commands = disable_system.get_all_commands()
            currently_disabled = set(disable_system.get_disabled_commands(channel_id))
            
            options = []
            for cmd in sorted(all_commands)[:25]:  # Discord limit 25 options
                is_disabled = cmd in currently_disabled
                options.append(discord.SelectOption(
                    label=f"+{cmd}",
                    value=cmd,
                    description="✅ Enabled" if not is_disabled else "❌ Disabled",
                    emoji="✅" if not is_disabled else "❌"
                ))
            
            super().__init__(
                placeholder="Chọn lệnh để disable/enable...",
                min_values=1,
                max_values=len(options),
                options=options
            )
        
        async def callback(self, interaction: discord.Interaction):
            disabled_count = 0
            enabled_count = 0
            
            for command in self.values:
                if disable_system.is_disabled(self.channel_id, command):
                    # Already disabled, enable it
                    disable_system.enable_command(self.channel_id, command)
                    enabled_count += 1
                else:
                    # Not disabled, disable it
                    disable_system.disable_command(self.channel_id, command)
                    disabled_count += 1
            
            msg = []
            if disabled_count > 0:
                msg.append(f"✅ Đã disable **{disabled_count}** lệnh")
            if enabled_count > 0:
                msg.append(f"✅ Đã enable **{enabled_count}** lệnh")
            
            await interaction.response.send_message("\n".join(msg), ephemeral=True)
    
    class DisableCommandView(discord.ui.View):
        def __init__(self, channel_id: str):
            super().__init__(timeout=60)
            self.add_item(DisableCommandSelect(channel_id))
    
    @bot.tree.command(name="disable", description="Vô hiệu hóa/kích hoạt lệnh trong kênh (Owner only)")
    async def disable_command_slash(interaction: discord.Interaction):
        # Check if user is owner
        if interaction.user.id not in OWNER_IDS:
            await interaction.response.send_message("❌ Chỉ owner mới được dùng lệnh này!", ephemeral=True)
            return
        
        channel_id = str(interaction.channel_id)
        view = DisableCommandView(channel_id)
        
        await interaction.response.send_message(
            "🔧 Chọn lệnh để toggle disable/enable:",
            view=view,
            ephemeral=True
        )
    
    @bot.tree.command(name="disabled", description="Xem danh sách lệnh bị vô hiệu hóa trong kênh này")
    async def list_disabled_slash(interaction: discord.Interaction):
        channel_id = str(interaction.channel_id)
        disabled = disable_system.get_disabled_commands(channel_id)
        
        if not disabled:
            await interaction.response.send_message("✅ Không có lệnh nào bị vô hiệu hóa trong kênh này!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🚫 Lệnh bị vô hiệu hóa trong #{interaction.channel.name}",
            description="\n".join([f"• `+{cmd}`" for cmd in disabled]),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(name="clearall", description="Xóa tất cả lệnh bị vô hiệu hóa trong kênh này (Owner only)")
    async def clear_disabled_slash(interaction: discord.Interaction):
        # Check if user is owner
        if interaction.user.id not in OWNER_IDS:
            await interaction.response.send_message("❌ Chỉ owner mới được dùng lệnh này!", ephemeral=True)
            return
        
        channel_id = str(interaction.channel_id)
        
        if disable_system.clear_channel(channel_id):
            await interaction.response.send_message("✅ Đã xóa tất cả lệnh bị vô hiệu hóa trong kênh này!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Không có lệnh nào bị vô hiệu hóa trong kênh này!", ephemeral=True)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        user_id = str(message.author.id)
        
        # Check if user is returning from AFK
        if afk_system.is_afk(user_id):
            duration = afk_system.get_afk_duration(user_id) or "vài giây"
            afk_data = afk_system.remove_afk(user_id)
            await message.channel.send(
                f"👋 Welcome back {message.author.mention}! Bạn đã AFK được **{duration}**",
                delete_after=5
            )
        
        # Check if message mentions someone who is AFK
        for mentioned in message.mentions:
            mentioned_id = str(mentioned.id)
            if afk_system.is_afk(mentioned_id):
                afk_data = afk_system.get_afk(mentioned_id)
                reason = afk_data.get("reason", "AFK")
                duration = afk_system.get_afk_duration(mentioned_id) or "vài giây"
                await message.channel.send(
                    f"💤 {mentioned.mention} đang AFK: **{reason}** (đã {duration})",
                    delete_after=10
                )

        try:
            await ai.ai_handle_message(bot, message)
        except Exception:
            logging.exception("Lỗi khi xử lý message bằng AI")

        await bot.process_commands(message)
