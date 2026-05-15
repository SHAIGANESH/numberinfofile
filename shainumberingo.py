import requests
import json
import asyncio
import time
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.constants import ParseMode

# === Flask app for health check ===
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# === CONFIGURATION ===
BOT_TOKEN = "8465239312:AAE2WJf_vBLe-iAFLEJCIlZ5B-MeaH434Yg"
API_URL = "https://movements-invoice-amanda-victoria.trycloudflare.com/search/number?number={}&key=mysecretkey123"

# === REQUIRED CHANNELS (MUST JOIN BEFORE USING BOT) ===
REQUIRED_CHANNELS = [
    {"username": "@shaidiss", "link": "https://t.me/shaidiss", "name": "SHAIDISS"},
    {"username": "@shairecord", "link": "https://t.me/shairecord", "name": "SHAIRECORD"}
]

OWNER_USERNAME = "@dinamic80"
OWNER_NAME = "NO RECORD"
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"

# === BOT IS NOW FREE ===
# No payment system - completely free for users who join channels
AUTO_DELETE_SECONDS = 30

# Store user data
user_data_store = {}

# Store which users have verified channel join
user_verified = {}

# Admin analytics
admin_analytics = {
    "daily": {},
    "monthly": {},
    "lifetime": {"total_searches": 0, "total_users": 0},
    "bot_start_time": datetime.now()
}

admin_authenticated = {}
BOT_START_TIME = datetime.now()

# === HELPER FUNCTIONS ===
def get_user_data(user_id: str):
    """Get or create user data"""
    now = datetime.now()
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "total_searches": 0,
            "search_history": [],
            "first_seen": now,
            "last_seen": now,
            "username": None,
            "first_name": None,
            "last_name": None
        }
        admin_analytics["lifetime"]["total_users"] = len(user_data_store)
    return user_data_store[user_id]

def update_user_info(user_id: str, update_obj: Update):
    """Update user info from Telegram update"""
    user_data = get_user_data(user_id)
    if update_obj.effective_user:
        user_data["username"] = update_obj.effective_user.username
        user_data["first_name"] = update_obj.effective_user.first_name
        user_data["last_name"] = update_obj.effective_user.last_name

async def check_membership(user_id: str, context: CallbackContext):
    """Check if user has joined all required channels"""
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = await context.bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            if chat_member.status in ["left", "kicked"]:
                return False, channel
        except Exception:
            return False, channel
    return True, None

def mark_verified(user_id: str):
    """Mark user as verified"""
    user_verified[user_id] = datetime.now()

def is_verified(user_id: str) -> bool:
    """Check if user is verified"""
    return user_id in user_verified

def log_search(user_id: str):
    """Log a search for analytics"""
    user_data = get_user_data(user_id)
    now = datetime.now()
    
    user_data["total_searches"] += 1
    user_data["search_history"].append(now)
    user_data["last_seen"] = now
    
    admin_analytics["lifetime"]["total_searches"] += 1
    
    date_key = now.strftime("%Y-%m-%d")
    if date_key not in admin_analytics["daily"]:
        admin_analytics["daily"][date_key] = {"count": 0, "users": set()}
    admin_analytics["daily"][date_key]["count"] += 1
    admin_analytics["daily"][date_key]["users"].add(user_id)
    
    month_key = now.strftime("%Y-%m")
    if month_key not in admin_analytics["monthly"]:
        admin_analytics["monthly"][month_key] = {"count": 0, "users": set()}
    admin_analytics["monthly"][month_key]["count"] += 1
    admin_analytics["monthly"][month_key]["users"].add(user_id)

def get_number_info(phone_number: str):
    url = API_URL.format(phone_number)
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("result"):
                return data["result"]
        return None
    except Exception:
        return None

async def delete_message_after_delay(context: CallbackContext, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

def get_join_keyboard():
    """Generate keyboard with required channels"""
    keyboard = []
    for channel in REQUIRED_CHANNELS:
        keyboard.append([InlineKeyboardButton(f"📢 Join {channel['name']}", url=channel["link"])])
    keyboard.append([InlineKeyboardButton("✅ I Have Joined Both", callback_data="verify_join")])
    keyboard.append([InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME[1:]}")])
    return InlineKeyboardMarkup(keyboard)

def get_main_keyboard():
    """Generate main bot keyboard"""
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel 1", url=REQUIRED_CHANNELS[0]["link"])],
        [InlineKeyboardButton("📢 Join Channel 2", url=REQUIRED_CHANNELS[1]["link"])],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
        [InlineKeyboardButton("📊 My Stats", callback_data="mystats")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# === ADMIN DECORATOR ===
def admin_required(func):
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = str(update.effective_user.id)
        if user_id != ADMIN_CHAT_ID and not admin_authenticated.get(user_id):
            await update.message.reply_text(
                f"🔒 *Admin Access Required*\n\nSend `/admin {ADMIN_PASSWORD}`\n\n👑 Owner: {OWNER_USERNAME}",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# === PING COMMAND ===
async def ping_command(update: Update, context: CallbackContext):
    start_time = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    end_time = time.time()
    latency = round((end_time - start_time) * 1000)
    
    uptime_seconds = (datetime.now() - BOT_START_TIME).total_seconds()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    
    await msg.edit_text(
        f"🏓 *Pong!*\n\n"
        f"📡 Latency: `{latency}ms`\n"
        f"⏱️ Bot Uptime: `{hours}h {minutes}m`\n"
        f"👥 Total Users: `{len(user_data_store)}`\n"
        f"🔍 Total Searches: `{admin_analytics['lifetime']['total_searches']}`\n"
        f"✅ Verified Users: `{len(user_verified)}`",
        parse_mode=ParseMode.MARKDOWN
    )

# === HELP COMMAND ===
async def help_command(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_data = get_user_data(user_id)
    
    help_text = f"""
🤖 *NUMBER INFO BOT - HELP GUIDE*

━━━━━━━━━━━━━━━━━━━━
📌 *REQUIREMENT*
━━━━━━━━━━━━━━━━━━━━

⚠️ You must join both channels to use this bot:
• @shaidiss
• @shairecord

━━━━━━━━━━━━━━━━━━━━
📌 *BASIC COMMANDS*
━━━━━━━━━━━━━━━━━━━━

/start - Start the bot
/help - Show this menu
/num <number> - Search number info
/mystats - Your search statistics
/ping - Check bot status

━━━━━━━━━━━━━━━━━━━━
📝 *HOW TO USE*
━━━━━━━━━━━━━━━━━━━━

1️⃣ Join both required channels
2️⃣ Click "✅ I Have Joined Both"
3️⃣ Send any 10-digit number
4️⃣ Or use `/num 9876543210`
5️⃣ Results auto-delete in {AUTO_DELETE_SECONDS}s

━━━━━━━━━━━━━━━━━━━━
📊 *YOUR STATS*
━━━━━━━━━━━━━━━━━━━━

✅ Total searches: `{user_data['total_searches']}`
📅 First seen: `{user_data['first_seen'].strftime('%Y-%m-%d')}`

━━━━━━━━━━━━━━━━━━━━
📢 *SUPPORT*
━━━━━━━━━━━━━━━━━━━━

👑 Owner: {OWNER_USERNAME}

*Bot is completely FREE!* 🎉
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# === USER COMMANDS ===
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = str(user.id)
    update_user_info(user_id, update)
    
    # Check if user is already verified
    if is_verified(user_id):
        # Show main menu
        keyboard = get_main_keyboard()
        await update.message.reply_text(
            f"✅ *Welcome Back!* {user.first_name}\n\n"
            f"🔍 *Number Info Bot*\n\n"
            f"Send any 10-digit number to get information.\n"
            f"Results auto-delete in {AUTO_DELETE_SECONDS} seconds.\n\n"
            f"📊 Your total searches: `{get_user_data(user_id)['total_searches']}`\n\n"
            f"📌 Use `/help` for commands.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return
    
    # Not verified - show join required message
    await update.message.reply_text(
        f"⚠️ *ACCESS REQUIRED* ⚠️\n\n"
        f"Hello {user.first_name}!\n\n"
        f"You must join the following channels to use this bot:\n\n"
        f"📢 @shaidiss\n"
        f"📢 @shairecord\n\n"
        f"👇 *Click the buttons below to join*\n\n"
        f"After joining both channels, click '✅ I Have Joined Both'.\n\n"
        f"*Bot is completely FREE for channel members!* 🎉",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_join_keyboard()
    )

async def mystats(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_data = get_user_data(user_id)
    
    await update.message.reply_text(
        f"📊 *YOUR STATISTICS*\n\n"
        f"✅ Total searches: `{user_data['total_searches']}`\n"
        f"📅 First used: `{user_data['first_seen'].strftime('%Y-%m-%d %H:%M')}`\n"
        f"🕒 Last used: `{user_data['last_seen'].strftime('%Y-%m-%d %H:%M')}`\n\n"
        f"📢 Joined channels: ✅ Verified\n"
        f"💵 *Bot is FREE!* 🎉",
        parse_mode=ParseMode.MARKDOWN
    )

async def num_command(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    args = context.args
    
    # Check verification first
    if not is_verified(user_id):
        await update.message.reply_text(
            f"⚠️ *Verification Required*\n\n"
            f"Please join both channels first:\n"
            f"• @shaidiss\n"
            f"• @shairecord\n\n"
            f"Then use `/start` again.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_join_keyboard()
        )
        return
    
    if len(args) != 1:
        await update.message.reply_text("❌ Usage: `/num 9876543210`\n\nSend a 10+ digit number.", parse_mode=ParseMode.MARKDOWN)
        return
    
    phone_number = ''.join(filter(str.isdigit, args[0]))
    if len(phone_number) < 10:
        await update.message.reply_text("❌ Please send a valid 10+ digit number.")
        return
    
    await process_number_search(update, context, phone_number, user_id)

async def process_number_search(update: Update, context: CallbackContext, phone_number: str, user_id: str):
    await update.message.chat.send_action(action="typing")
    
    info = get_number_info(phone_number)
    
    if not info:
        await update.message.reply_text("⚠️ No information found for this number.")
        return
    
    # Log the search
    log_search(user_id)
    user_data = get_user_data(user_id)
    
    record = info[0] if isinstance(info, list) and info else info
    
    result_message = f"""
🔍 *NUMBER SEARCH RESULT*

━━━━━━━━━━━━━━━━━━━━
📱 *Number:* `{phone_number}`
━━━━━━━━━━━━━━━━━━━━

👤 Name: `{record.get('name', 'N/A')}`
📛 First Name: `{record.get('fname', 'N/A')}`
📱 Mobile: `{record.get('num', phone_number)}`
🔄 Alternate: `{record.get('alt', 'N/A')}`
📍 Address: `{record.get('address', 'N/A')}`
📡 Circle: `{record.get('circle', 'N/A')}`
🆔 Aadhar: `{record.get('aadhar', 'N/A')}`
✉️ Email: `{record.get('email', 'N/A')}`

━━━━━━━━━━━━━━━━━━━━
📊 *YOUR STATS*
━━━━━━━━━━━━━━━━━━━━

✅ Total searches: `{user_data['total_searches']}`

━━━━━━━━━━━━━━━━━━━━
⚡ Auto-delete in {AUTO_DELETE_SECONDS}s
🎉 *Bot is FREE!*
"""
    
    msg = await update.message.reply_text(result_message, parse_mode=ParseMode.MARKDOWN)
    
    asyncio.create_task(delete_message_after_delay(context, msg.chat_id, msg.message_id, AUTO_DELETE_SECONDS))
    asyncio.create_task(delete_message_after_delay(context, update.message.chat_id, update.message.message_id, AUTO_DELETE_SECONDS))

async def handle_number(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    update_user_info(user_id, update)
    
    # Check verification first
    if not is_verified(user_id):
        await update.message.reply_text(
            f"⚠️ *Verification Required*\n\n"
            f"Please join both channels first:\n"
            f"• @shaidiss\n"
            f"• @shairecord\n\n"
            f"Then click '✅ I Have Joined Both' button below.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_join_keyboard()
        )
        return
    
    user_input = update.message.text.strip()
    phone_number = ''.join(filter(str.isdigit, user_input))
    
    if len(phone_number) < 10:
        await update.message.reply_text("❌ Send a valid 10+ digit number.\n\nExample: `9876543210`", parse_mode=ParseMode.MARKDOWN)
        return
    
    await process_number_search(update, context, phone_number, user_id)

# === VERIFICATION HANDLER ===
async def verify_join(update: Update, context: CallbackContext):
    """Handle user verification after joining channels"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    # Check if user has joined both channels
    is_member, missing_channel = await check_membership(user_id, context)
    
    if is_member:
        mark_verified(user_id)
        user_data = get_user_data(user_id)
        
        keyboard = get_main_keyboard()
        
        await query.message.edit_text(
            f"✅ *VERIFICATION SUCCESSFUL!*\n\n"
            f"Welcome {query.from_user.first_name}!\n\n"
            f"🔍 You can now use the bot.\n\n"
            f"📊 Your total searches: `{user_data['total_searches']}`\n\n"
            f"Send any 10-digit number to get information.\n"
            f"Results auto-delete in {AUTO_DELETE_SECONDS} seconds.\n\n"
            f"🎉 *Bot is completely FREE!*\n\n"
            f"📌 Use `/help` for commands.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    else:
        channel_name = missing_channel["name"] if missing_channel else "both channels"
        await query.message.edit_text(
            f"⚠️ *VERIFICATION FAILED*\n\n"
            f"❌ You have not joined: **{channel_name}**\n\n"
            f"Please join both channels first:\n"
            f"📢 @shaidiss\n"
            f"📢 @shairecord\n\n"
            f"After joining, click the verify button again.\n\n"
            f"*Bot is FREE for channel members!* 🎉",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_join_keyboard()
        )

# === ADMIN COMMANDS ===
async def admin_login(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    args = context.args
    
    if len(args) != 1:
        await update.message.reply_text(
            f"❌ *Admin Login*\n\nUsage: `/admin {ADMIN_PASSWORD}`\n\n👑 Owner: {OWNER_USERNAME}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if args[0] == ADMIN_PASSWORD:
        admin_authenticated[user_id] = True
        
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("📅 Daily", callback_data="admin_daily")],
            [InlineKeyboardButton("📆 Monthly", callback_data="admin_monthly")],
            [InlineKeyboardButton("🏆 Lifetime", callback_data="admin_lifetime")],
            [InlineKeyboardButton("👤 User Info", callback_data="admin_userinfo")],
            [InlineKeyboardButton("📋 All Users", callback_data="admin_users")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔒 Logout", callback_data="admin_logout")]
        ]
        
        await update.message.reply_text(
            f"✅ *ADMIN ACCESS GRANTED*\n\n"
            f"👑 Welcome {OWNER_NAME}\n\n"
            f"📊 *Bot Status*\n"
            f"• Users: `{len(user_data_store)}`\n"
            f"• Verified: `{len(user_verified)}`\n"
            f"• Searches: `{admin_analytics['lifetime']['total_searches']}`\n\n"
            f"📋 *Commands:* `/admincmds`\n\n"
            f"📢 Required Channels:\n"
            f"• @shaidiss\n"
            f"• @shairecord",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("❌ *Incorrect password!*", parse_mode=ParseMode.MARKDOWN)

async def admin_logout(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id in admin_authenticated:
        del admin_authenticated[user_id]
        await update.message.reply_text("🔒 *Admin session ended.*", parse_mode=ParseMode.MARKDOWN)

@admin_required
async def admin_stats(update: Update, context: CallbackContext):
    total_users = len(user_data_store)
    verified_users = len(user_verified)
    total_searches = admin_analytics["lifetime"]["total_searches"]
    today = datetime.now().strftime("%Y-%m-%d")
    today_stats = admin_analytics["daily"].get(today, {"count": 0})
    
    await update.message.reply_text(
        f"📊 *BOT STATISTICS*\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"✅ Verified Users: `{verified_users}`\n"
        f"🔍 Total Searches: `{total_searches}`\n\n"
        f"📅 Today: `{today_stats['count']}` searches\n\n"
        f"📢 Required Channels:\n"
        f"• @shaidiss\n"
        f"• @shairecord\n\n"
        f"🎉 *Bot is FREE!*",
        parse_mode=ParseMode.MARKDOWN
    )

@admin_required
async def admin_daily(update: Update, context: CallbackContext):
    today = datetime.now().strftime("%Y-%m-%d")
    stats = admin_analytics["daily"].get(today, {"count": 0, "users": set()})
    
    await update.message.reply_text(
        f"📅 *DAILY REPORT* – {today}\n\n"
        f"🔍 Searches: `{stats['count']}`\n"
        f"👥 Active Users: `{len(stats['users'])}`",
        parse_mode=ParseMode.MARKDOWN
    )

@admin_required
async def admin_monthly(update: Update, context: CallbackContext):
    month = datetime.now().strftime("%Y-%m")
    stats = admin_analytics["monthly"].get(month, {"count": 0, "users": set()})
    
    await update.message.reply_text(
        f"📆 *MONTHLY REPORT* – {month}\n\n"
        f"🔍 Searches: `{stats['count']}`\n"
        f"👥 Active Users: `{len(stats['users'])}`",
        parse_mode=ParseMode.MARKDOWN
    )

@admin_required
async def admin_lifetime(update: Update, context: CallbackContext):
    uptime = datetime.now() - BOT_START_TIME
    hours = int(uptime.total_seconds() // 3600)
    
    await update.message.reply_text(
        f"🏆 *LIFETIME STATISTICS*\n\n"
        f"👥 Total Users: `{admin_analytics['lifetime']['total_users']}`\n"
        f"✅ Verified: `{len(user_verified)}`\n"
        f"🔍 Total Searches: `{admin_analytics['lifetime']['total_searches']}`\n"
        f"⏱️ Bot Uptime: `{hours}` hours\n\n"
        f"📢 Required: @shaidiss & @shairecord\n"
        f"🎉 *Bot is FREE!*",
        parse_mode=ParseMode.MARKDOWN
    )

@admin_required
async def admin_userinfo(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "❌ Usage: `/userinfo <user_id>`\n\n"
            "Or `/userinfo @username`\n\n"
            "📋 To see all users: `/users`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    target = args[0]
    target_user = None
    
    if target.startswith("@"):
        username = target[1:].lower()
        for uid, data in user_data_store.items():
            if data.get("username") and data["username"].lower() == username:
                target_user = uid
                break
    else:
        target_user = target
    
    if not target_user or target_user not in user_data_store:
        await update.message.reply_text(f"❌ User `{target}` not found", parse_mode=ParseMode.MARKDOWN)
        return
    
    user_data = user_data_store[target_user]
    is_verified_user = is_verified(target_user)
    
    user_info_text = f"""
👤 *USER INFORMATION*

━━━━━━━━━━━━━━━━━━━━
🆔 *User ID:* `{target_user}`
━━━━━━━━━━━━━━━━━━━━

📛 Name: `{user_data.get('first_name', 'N/A')} {user_data.get('last_name', '')}`
👤 Username: @{user_data.get('username', 'N/A')}
✅ Verified: `{'Yes' if is_verified_user else 'No'}`

━━━━━━━━━━━━━━━━━━━━
📊 *SEARCH STATS*
━━━━━━━━━━━━━━━━━━━━

✅ Total searches: `{user_data['total_searches']}`

━━━━━━━━━━━━━━━━━━━━
📅 *ACTIVITY*
━━━━━━━━━━━━━━━━━━━━

📅 First seen: `{user_data['first_seen'].strftime('%Y-%m-%d %H:%M')}`
🕒 Last seen: `{user_data['last_seen'].strftime('%Y-%m-%d %H:%M')}`
"""
    await update.message.reply_text(user_info_text, parse_mode=ParseMode.MARKDOWN)

@admin_required
async def admin_users(update: Update, context: CallbackContext):
    """Show all users list"""
    if not user_data_store:
        await update.message.reply_text("No users yet.")
        return
    
    user_list = "📋 *ALL USERS LIST*\n\n"
    for uid, data in list(user_data_store.items())[:20]:
        name = data.get('first_name', 'Unknown')
        username = f"@{data.get('username')}" if data.get('username') else "No username"
        verified = "✅" if is_verified(uid) else "❌"
        searches = data['total_searches']
        user_list += f"{verified} `{uid}` - {name} - {searches} searches\n"
    
    if len(user_data_store) > 20:
        user_list += f"\n... and {len(user_data_store) - 20} more users"
    
    user_list += f"\n\n📌 Total: `{len(user_data_store)}` users"
    user_list += f"\n✅ Verified: `{len(user_verified)}` users"
    
    await update.message.reply_text(user_list, parse_mode=ParseMode.MARKDOWN)

@admin_required
async def admin_broadcast(update: Update, context: CallbackContext):
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("❌ Usage: `/broadcast <message>`")
        return
    
    success_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text("📢 Broadcasting...")
    
    for user_id in user_data_store.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *ANNOUNCEMENT*\n\n{message}\n\n─\n👑 {OWNER_NAME}\n📢 @shaidiss | @shairecord",
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1
    
    await status_msg.edit_text(
        f"📢 *Broadcast Complete*\n\n"
        f"✅ Success: `{success_count}`\n"
        f"❌ Failed: `{fail_count}`",
        parse_mode=ParseMode.MARKDOWN
    )

@admin_required
async def admin_commands(update: Update, context: CallbackContext):
    await update.message.reply_text(
        f"👑 *ADMIN COMMANDS*\n\n"
        f"📊 `/stats` - Quick statistics\n"
        f"📅 `/daily` - Daily report\n"
        f"📆 `/monthly` - Monthly report\n"
        f"🏆 `/lifetime` - Lifetime stats\n"
        f"👤 `/userinfo <id|@username>` - User details\n"
        f"📋 `/users` - List all users\n"
        f"📢 `/broadcast <msg>` - Send to all\n"
        f"🏓 `/ping` - Check bot status\n"
        f"🔒 `/logout` - End session\n\n"
        f"📢 Required Channels:\n"
        f"• @shaidiss\n"
        f"• @shairecord\n\n"
        f"👥 Total Users: `{len(user_data_store)}`\n"
        f"✅ Verified: `{len(user_verified)}`\n"
        f"🎉 *Bot is FREE!*",
        parse_mode=ParseMode.MARKDOWN
    )

# === BUTTON CALLBACKS ===
async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    # Verification button
    if query.data == "verify_join":
        await verify_join(update, context)
    
    # User buttons
    elif query.data == "mystats":
        user_data = get_user_data(user_id)
        await query.message.reply_text(
            f"📊 *YOUR STATISTICS*\n\n"
            f"✅ Total searches: `{user_data['total_searches']}`\n"
            f"📅 First used: `{user_data['first_seen'].strftime('%Y-%m-%d %H:%M')}`\n"
            f"🕒 Last used: `{user_data['last_seen'].strftime('%Y-%m-%d %H:%M')}`\n\n"
            f"🎉 *Bot is FREE!*",
            parse_mode=ParseMode.MARKDOWN
        )
    elif query.data == "help":
        await help_command(update, context)
    
    # Admin buttons
    elif query.data == "admin_stats":
        await admin_stats(update, context)
    elif query.data == "admin_daily":
        await admin_daily(update, context)
    elif query.data == "admin_monthly":
        await admin_monthly(update, context)
    elif query.data == "admin_lifetime":
        await admin_lifetime(update, context)
    elif query.data == "admin_userinfo":
        await query.message.reply_text(
            "Send `/userinfo <user_id>`\n"
            "Example: `/userinfo 8481566006`\n\n"
            "Or `/userinfo @username`"
        )
    elif query.data == "admin_users":
        await admin_users(update, context)
    elif query.data == "admin_broadcast":
        await query.message.reply_text("Send `/broadcast <your message>`")
    elif query.data == "admin_logout":
        if user_id in admin_authenticated:
            del admin_authenticated[user_id]
            await query.message.reply_text("🔒 Logged out.")

# === MAIN ===
def main():
    Thread(target=run_flask).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("num", num_command))
    app.add_handler(CommandHandler("mystats", mystats))
    app.add_handler(CommandHandler("ping", ping_command))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("logout", admin_logout))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("daily", admin_daily))
    app.add_handler(CommandHandler("monthly", admin_monthly))
    app.add_handler(CommandHandler("lifetime", admin_lifetime))
    app.add_handler(CommandHandler("userinfo", admin_userinfo))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("admincmds", admin_commands))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ BOT STARTED SUCCESSFULLY!")
    print(f"   - Required Channels: @shaidiss, @shairecord")
    print(f"   - Bot is FREE for channel members")
    print(f"   - Auto-delete in {AUTO_DELETE_SECONDS} seconds")
    print(f"   - /num command available")
    print(f"   - /help command available")
    print(f"   - Admin commands ready")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, timeout=30)

if __name__ == "__main__":
    main()
