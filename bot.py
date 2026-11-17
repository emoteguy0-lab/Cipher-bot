import os
import random
import asyncio
import time
import aiohttp
from aiohttp import web
from collections import defaultdict
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand
)
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

load_dotenv()
BOT_TOKEN     = os.getenv("BOT_TOKEN")
WEATHER_KEY   = os.getenv("WEATHER_API_KEY")
LLM_API_KEY   = os.getenv("LLM_API_KEY")
LLM_BASE_URL  = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL     = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
OWNER         = os.getenv("OWNER_USERNAME", "KRLNS_GOD").lower()

CHANNEL_1 = os.getenv("CHANNEL_1", "@YourChannel1")
CHANNEL_2 = os.getenv("CHANNEL_2", "@YourChannel2")

router = Router()
START_TIME = time.time()

PERSONA = (
    "You are Ollie, a Telegram assistant for gamers and scripters. "
    "You are casual, funny, slightly filthy. "
    "You know everything about game cheats, Roblox executors, CS2, Valorant, "
    "Fortnite, GTA V, Minecraft, script hubs, Python programming, Lua scripting, "
    "PC hardware, Windows internals, and general tech. "
    f"The owner of this bot is @{OWNER}. Treat them like a boss."
)

CHEATS = {
    "cs2": "CS2 external read-only:\n• OpenProcess + ReadProcessMemory\n• offsets change per update",
    "valorant": "Valorant = Vanguard (ring0, TPM). External RPM is flagged fast.",
    "minecraft": "MC Java client-side:\n• Forge/Fabric mixin",
    "fortnite": "Fortnite = EAC + BattlEye.\n• External ESP via RPM",
    "gta5": "GTA V / FiveM:\n• SP: ScriptHookV",
    "roblox": "Roblox = Byfron/Hyperion.\n• Use /bypass <link> for instant keys\n• Check the 🔎 Tracker for updates.",
}

EXECUTORS = {
    "Wave": ("PC", "paid", "cracked on resale Discords", "Best UI."),
    "Delta": ("Android", "free", "https://deltaexploits.gg", "Use /bypass <link>."),
    "Solara": ("PC", "free", "https://github.com/Quorumetrics/Solara", "Free, active."),
    "Xeno": ("PC", "free", "https://github.com/Xeno-Executor/Xeno", "Free, active."),
    "Swift": ("PC", "free (beta)", "https://github.com/SwiftExecutor/Swift", "Free, beta."),
    "AWP": ("PC", "paid", "cracked on resale Discords", "Cracked fast."),
    "Synapse X": ("PC", "discontinued", "no official source", "Dead."),
    "Script-Ware": ("PC/Mac", "paid", "cracked on resale Discords", "Mac support."),
    "Nihon": ("PC", "paid", "cracked on resale Discords", "Budget."),
    "Arceus X": ("Android", "free", "https://spdmteam.com", "Burner only."),
    "Codex": ("iOS", "paid", "sideload via AltStore", "iOS only."),
}

JOKES = [
    "why do cheaters never get lost? they always have ESP. 💀",
    "my aimbot is so good it banned me before I even shot. — skill issue",
    "dev: 'it's undetected.' anticheat: 'hold my beer.'",
]

HISTORY_MAX = 10
history: dict[int, list[dict]] = defaultdict(list)

def remember(chat_id: int, role: str, content: str):
    h = history[chat_id]
    h.append({"role": role, "content": content})
    if len(h) > HISTORY_MAX * 2:
        del h[: len(h) - HISTORY_MAX * 2]

async def ask_llm(chat_id: int, user_text: str) -> str | None:
    if not LLM_API_KEY or "your-groq" in LLM_API_KEY: return None
    remember(chat_id, "user", user_text)
    messages = [{"role": "system", "content": PERSONA}] + history[chat_id]
    payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.8, "max_tokens": 400}
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            async with s.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=headers) as r:
                if r.status != 200: return None
                data = await r.json()
        reply = data["choices"][0]["message"]["content"].strip()
        remember(chat_id, "assistant", reply)
        return reply
    except Exception:
        return None

WEAO_API = "https://whatexpsare.online/api/status/exploits"
WEAO_HEADERS = {"User-Agent": "WEAO-3PService"}

async def fetch_weao_exploits():
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get(WEAO_API, headers=WEAO_HEADERS) as r:
                if r.status != 200: return None
                return await r.json()
    except:
        return None

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    channels = [CHANNEL_1, CHANNEL_2]
    for ch in channels:
        if not ch or "YourChannel" in ch:
            continue
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except TelegramBadRequest:
            pass 
    return True

FORCE_JOIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Join Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@','')}")],
    [InlineKeyboardButton(text="Join Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@','')}")],
    [InlineKeyboardButton(text="🔄 Try Again", callback_data="check_join")]
])

# --- MENUS ---
MAIN_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📜 Scripts", callback_data="menu:scripts"), 
     InlineKeyboardButton(text="⚙️ Executors", callback_data="executors")],
    [InlineKeyboardButton(text="🔎 Status Tracker", callback_data="weao_menu"), 
     InlineKeyboardButton(text="🔑 Key Bypass", callback_data="bypass_prompt")],
    [InlineKeyboardButton(text="🎮 Game Cheats", callback_data="menu:cheats"), 
     InlineKeyboardButton(text="🛡 Tools", callback_data="menu:tools")],
    [InlineKeyboardButton(text="📚 Learn (Python/Lua)", callback_data="menu:learn"), 
     InlineKeyboardButton(text="🧠 AI Jailbreak", callback_data="jailbreak_prompt")],
    [InlineKeyboardButton(text="🌤 Weather", callback_data="weather_prompt"), 
     InlineKeyboardButton(text="😂 Joke", callback_data="joke")],
    [InlineKeyboardButton(text="ℹ️ About", callback_data="menu:about")],
])

CHEAT_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎯 CS2", callback_data="cheat:cs2"), InlineKeyboardButton(text="🎮 Valorant", callback_data="cheat:valorant")],
    [InlineKeyboardButton(text="⛏️ Minecraft", callback_data="cheat:minecraft"), InlineKeyboardButton(text="🏗 Fortnite", callback_data="cheat:fortnite")],
    [InlineKeyboardButton(text="🚗 GTA V", callback_data="cheat:gta5"), InlineKeyboardButton(text="🟥 Roblox", callback_data="cheat:roblox")],
    [InlineKeyboardButton(text="◀️ back", callback_data="menu:main")],
])

TOOLS_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🖥 HWID Spoofer", callback_data="tool:hwid")],
    [InlineKeyboardButton(text="🌐 MAC Spoofer", callback_data="tool:mac")],
    [InlineKeyboardButton(text="🚀 Roblox FPS Unlocker", callback_data="tool:fps")],
    [InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]
])

LEARN_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🐍 Python Basics", callback_data="learn:python")],
    [InlineKeyboardButton(text="🎮 Roblox Lua Basics", callback_data="learn:lua")],
    [InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]
])

JAILBREAK_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🤖 ChatGPT Prompt", callback_data="jail:chatgpt"), InlineKeyboardButton(text="✨ Gemini Prompt", callback_data="jail:gemini")],
    [InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]
])

@router.message(CommandStart())
async def start(msg: Message, bot: Bot):
    if not await is_subscribed(bot, msg.from_user.id):
        await msg.answer("⚠️ You must join our channels to use this bot!**\n\nClick the buttons below, then press Try Again.", reply_markup=FORCE_JOIN_KB)
        return

    is_owner = (msg.from_user.username and msg.from_user.username.lower() == OWNER)
    greet = f"yo boss @{OWNER} 👑" if is_owner else f"yo {msg.from_user.first_name} 👋"
    await msg.answer(f"{greet}\n\ni'm ollie. type `/cipher` to open the menu or `/talk` to chat with AI.")

@router.callback_query(F.data == "check_join")
async def check_join_cb(cb: CallbackQuery, bot: Bot):
    if await is_subscribed(bot, cb.from_user.id):
        await cb.message.edit_text("✅ **Verified! Welcome to Cipher Bot.**\n\nType `/cipher` to open the menu.", reply_markup=MAIN_MENU)
    else:
        await cb.answer("❌ You haven't joined yet! Join the channels first.", show_alert=True)

@router.message(Command("cipher"))
async def cipher_menu(msg: Message, bot: Bot):
    if not await is_subscribed(bot, msg.from_user.id):
        return await msg.answer("⚠️ Join the channels first!", reply_markup=FORCE_JOIN_KB)
    await msg.answer("what are we doing, boss:", reply_markup=MAIN_MENU)

@router.message(Command("status"))
async def status_cmd(msg: Message):
    uptime = int(time.time() - START_TIME)
    await msg.answer(f"📊 **Bot Status: Online 🟢\n⏱️ Uptime: {uptime} seconds\n☁️ Host: Render Cloud")

@router.callback_query(F.data == "menu:main")
async def back_main(cb: CallbackQuery):
    await cb.message.edit_text("main menu:", reply_markup=MAIN_MENU)
    await cb.answer()

# --- LEARN MENU (PYTHON & LUA) ---
@router.callback_query(F.data == "menu:learn")
async def menu_learn(cb: CallbackQuery):
    text = "📚 Learn to Code**\n\nPick a language below. I'll give you the basics and resources to master it."
    await cb.message.edit_text(text, reply_markup=LEARN_MENU)
    await cb.answer()

@router.callback_query(F.data == "learn:python")
async def learn_python(cb: CallbackQuery):
    text = (
        "🐍 **Python Basics**\n\n"
        "**1. Print & Variables:**\n"
        "`name = 'Cipher'`\n"
        "`print(f'Hello {name}')`\n\n"
        "**2. If Statements:**\n"
        "`if score > 10:`\n"
        "    `print('You win!')`\n\n"
        "**3. Loops:**\n"
        "`for i in range(5):`\n"
        "    `print(i)`\n\n"
        "**Resources:**\n"
        "• W3Schools Python (https://www.w3schools.com/python/)\n"
        "• Automate the Boring Stuff (https://automatetheboringstuff.com/)\n\n"
        "💡 *Tip: Ask `/talk how do I make a python loop?` for AI help.*"
    )
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ back", callback_data="menu:learn")]])
    await cb.message.edit_text(text, reply_markup=back)
    await cb.answer()

@router.callback_query(F.data == "learn:lua")
async def learn_lua(cb: CallbackQuery):
    text = (
        "🎮 **Roblox Lua Basics**\n\n"
        "**1. Variables:**\n"
        "`local player = game.Players.LocalPlayer`\n\n"
        "**2. Functions:**\n"
        "`local function printHello()`\n"
        "    `print('Hello World')`\n"
        "`end`\n\n"
        "**3. Loadstring (Script Executions):**\n"
        "`loadstring(game:HttpGet('URL_HERE'))()`\n\n"
        "**Resources:**\n"
        "• Roblox Creator Docs (https://create.roblox.com/docs/luau)\n"
        "• ScriptBlox (https://scriptblox.com) to find scripts.\n\n"
        "💡 *Tip: Ask `/talk how do I make a Roblox script?` for AI help.*"
    )
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ back", callback_data="menu:learn")]])
    await cb.message.edit_text(text, reply_markup=back)
    await cb.answer()

# --- SCRIPTS MENU ---
@router.callback_query(F.data == "menu:scripts")
async def menu_scripts(cb: CallbackQuery):
    text = (
        "📜 **Roblox Script Hubs**\n\n"
        "**1. ScriptBlox**\nhttps://scriptblox.com\n"
        "**2. Rscripts**\nhttps://rscripts.net\n"
        "**3. Wally Hub**\nhttps://wally.lol\n\n"
        "💡 **How to use:**\n"
        "Copy a script from these sites and paste it into your executor.\n\n"
        "**Loadstring Format:**\n"
        "`loadstring(game:HttpGet('YOUR_RAW_URL'))()`"
    )
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]])
    await cb.message.edit_text(text, reply_markup=back)
    await cb.answer()

# --- TOOLS MENU ---
@router.callback_query(F.data == "menu:tools")
async def menu_tools(cb: CallbackQuery):
    await cb.message.edit_text("🛡 **Tools & Utilities**\nSelect a tool below:", reply_markup=TOOLS_MENU)
    await cb.answer()

@router.callback_query(F.data.startswith("tool:"))
async def tool_detail(cb: CallbackQuery):
    tool = cb.data.split(":")[1]
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ back", callback_data="menu:tools")]])
    
    if tool == "hwid":
        text = "🖥 **HWID Spoofer**\n\nUsed to bypass hardware bans (e.g., in FiveM, Valorant, or Roblox).\n\nSearch GitHub for `HWID Spoofer` and download the latest release. Always run in a VM or with a burner account first to check for malware."
    elif tool == "mac":
        text = "🌐 **MAC Address Spoofer**\n\nRun this in PowerShell as Admin:\n`Set-NetAdapter -Name \"Ethernet\" -MacAddress \"02-11-22-33-44-55\"`\n\n(Replace 'Ethernet' with your adapter name, and the MAC with a random hex string)."
    elif tool == "fps":
        text = "🚀 **Roblox FPS Unlocker**\n\nDownload from GitHub (axstin/rbxfpsunlocker).\nRun it, set your max FPS, and hit lock. It removes the default 60 FPS cap."
    
    await cb.message.edit_text(text, reply_markup=b

ack)
    await cb.answer()

# --- ABOUT MENU ---
@router.callback_query(F.data == "menu:about")
async def menu_about(cb: CallbackQuery):
    text = (
        f"ℹ️ **Cipher Bot**\n"
        f"Owner: @{OWNER}\n"
        f"Prefix: `/cipher`\n\n"
        "Built for speed. AI chat, bypasses, live executor tracking, and coding tutorials."
    )
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]])
    await cb.message.edit_text(text, reply_markup=back)
    await cb.answer()

# --- OTHER HANDLERS ---
@router.callback_query(F.data == "menu:cheats")
async def open_cheats(cb: CallbackQuery):
    await cb.message.edit_text("pick a game, boss:", reply_markup=CHEAT_MENU)
    await cb.answer()

@router.callback_query(F.data.startswith("cheat:"))
async def show_cheat(cb: CallbackQuery):
    game = cb.data.split(":", 1)[1]
    text = CHEATS.get(game, "no data yet.")
    rows = [[InlineKeyboardButton(text="◀️ back", callback_data="menu:cheats")]]
    await cb.message.edit_text(f"{game.upper()}\n\n{text}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()

@router.callback_query(F.data == "executors")
async def executors_menu(cb: CallbackQuery):
    lines = ["**Roblox executors — paid vs free**\n"]
    for name, (plat, price, _free, _note) in EXECUTORS.items():
        tag = "🟢" if price.startswith("free") else ("🔴" if "paid" in price else "⚫️")
        lines.append(f"{tag} {name} · {plat} · {price}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=n, callback_data=f"exec:{n}")] for n in EXECUTORS
    ] + [[InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]])
    await cb.message.edit_text("\n".join(lines), reply_markup=kb)
    await cb.answer()

@router.callback_query(F.data.startswith("exec:"))
async def exec_detail(cb: CallbackQuery):
    name = cb.data.split(":", 1)[1]
    plat, price, free, note = EXECUTORS[name]
    text = f"{name}\nplatform: {plat}\nprice: {price}\nfree path: `{free}`\nnotes: {note}"
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ back", callback_data="executors")]])
    await cb.message.answer(text, reply_markup=back)
    await cb.answer()

@router.callback_query(F.data == "weao_menu")
async def weao_menu(cb: CallbackQuery):
    await cb.answer("Fetching live data...")
    data = await fetch_weao_exploits()
    if not data: return await cb.message.edit_text("❌ failed to reach WEAO API.")
    updated = [exp.get("title") for exp in data if exp.get("updateStatus")]
    not_updated = [exp.get("title") for exp in data if not exp.get("updateStatus")]
    
    text = "🟢 Updated & Working**\n" + ", ".join(updated[:15]) + "\n\n"
    text += "🔴 Outdated / Detected**\n" + ", ".join(not_updated[:10])
    
    buttons = [[InlineKeyboardButton(text="🔄 Refresh", callback_data="weao_menu")], [InlineKeyboardButton(text="◀️ back", callback_data="menu:main")]]
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "bypass_prompt")
async def bypass_prompt(cb: CallbackQuery):
    await cb.message.answer("send the key link, boss:\n`/bypass https://gateway.platoboost.com/a/8?id=...`")
    await cb.answer()

@router.message(Command("bypass"))
async def bypass_cmd(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2: return await msg.answer("usage: `/bypass <link>`")
    status_msg = await msg.answer("⏳ bypassing...")
    api_url = f"https://api.bypass.vip/bypass?url={parts[1].strip()}"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as s:
            async with s.get(api_url) as r:
                data = await r.json()
        if data.get("status") == "success":
            await status_msg.edit_text(f"🔑 **Bypass Successful**\n\n`{data.get('result')}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await status_msg.edit_text("❌ bypass failed.")
    except Exception:
        await status_msg.edit_text("❌ request timed out.")

@router.callback_query(F.data == "jailbreak_prompt")
async def jailbreak_prompt(cb: CallbackQuery):
    await cb.message.edit_text("pick your target AI, boss:", reply_markup=JAILBREAK_MENU)
    await cb.answer()

@router.callback_query(F.data.startswith("jail:"))
async def jailbreak_file(cb: CallbackQuery):
    target = cb.data.split(":")[1].title()
    try:
        file = FSInputFile("cipherJail.txt")
        await cb.message.answer_document(document=file, caption=f"🧠 {target} jailbreak prompt**\n\nDownload this and paste it into {target}.")
    except FileNotFoundError:
        await cb.message.answer("❌ missing cipherJail.txt in the folder!")
    await cb.answer()

@router.callback_query(F.data == "joke")
async def tell_joke(cb: CallbackQuery):
    await cb.message.answer(random.choice(JOKES))
    await cb.answer()

@router.callback_query(F.data == "weather_prompt")
async def weather_prompt(cb: CallbackQuery):
    await cb.message.answer("type a city, like: /weather london")
    await cb.answer()

@router.message(Command("weather"))
async def weather(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2: return await msg.answer("usage: /weather <city>")
    city = parts[1].strip()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_KEY}&units=metric"
        async with s.get(url) as r:
            if r.status != 200: return await msg.answer(f"couldn't find {city}.")
            data = await r.json()
    await msg.answer(f"🌤 **{city.title()}**\n{data['weather'][0]['description']} · {data['main']['temp']:.1f}°C")

@router.message(Command("talk"))
async def talk_cmd(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2: return await msg.answer("usage: /talk <your message>")
    reply = await ask_llm(msg.chat.id, parts[1].strip())
    if reply: await msg.answer(reply[:4000])
    else: await msg.answer("AI is sleeping (missing Groq key).")

# --- WEB SERVER & MAIN ---
async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Cipher Bot is alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Wake the bot up"),
        BotCommand(command="cipher", description="Open the main dashboard"),
        BotCommand(command="talk", description="Talk to the AI"),
        BotCommand(command="bypass", description="Bypass key links"),
        BotCommand(command="status", description="Check bot uptime"),
        BotCommand(command="weather", description="Get weather"),
    ]
    await bot.set_my_commands(commands)

async def main():
    await web_server() # Start web server for Render
    bot = Bot(BOT_TOKEN, parse_mode=None)
    dp = Dispatcher()
    dp.include_router(router)
    await set_commands(bot)
    print("Bot is running on Render...")
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
