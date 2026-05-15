import requests
import json
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

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
CHANNEL_ID = "https://t.me/norecorddis"
OWNER_USERNAME = "@dinamic80"
OWNER_NAME = "NO RECORD"
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"

# === SEARCH LIMIT CONFIGURATION ===
MAX_SEARCHES_PER_USER = 5
RESET_HOURS = 24

# Store user search data
user_data_store = {}

# Store admin analytics
admin_analytics = {
    "daily": {},
    "monthly": {},
    "lifetime": {"total_searches": 0, "total_users": 0}
}

admin_authenticated = {}

# === HELPER FUNCTIONS ===
def get_user_data(user_id: str):
    """Get or create user data"""
    now = datetime.now()
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "remaining": MAX_SEARCHES_PER_USER,
            "reset_time": now + timedelta(hours=RESET_HOURS),
            "search_history": [],
            "total_searches": 0,
            "first_seen": now
        }
        admin_analytics["lifetime"]["total_users"] = len(user_data_store)
    return user_data_store[user_id]

def get_user_remaining(user_id: str):
    """Get remaining searches, auto-reset if needed"""
    user_data = get_user_data(user_id)
    now = datetime.now()
    
    if now >= user_data["reset_time"]:
        user_data["remaining"] = MAX_SEARCHES_PER_USER
        user_data["reset_time"] = now + timedelta(hours=RESET_HOURS)
    
    return user_data["remaining"]

def decrement_user_search(user_id: str):
    """Decrease remaining count and log search"""
    user_data = get_user_data(user_id)
    now = datetime.now()
    
    if now >= user_data["reset_time"]:
        user_data["remaining"] = MAX_SEARCHES_PER_USER - 1
        user_data["reset_time"] = now + timedelta(hours=RESET_HOURS)
    else:
        user_data["remaining"] -= 1
    
    user_data["search_history"].append(now)
    user_data["total_searches"] += 1
    
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

def get_reset_time_left(user_id: str):
    """Get remaining time until reset"""
    user_data = get_user_data(user_id)
    remaining = user_data["reset_time"] - datetime.now()
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return f"{hours}h {minutes}m"

def get_number_info(phone_number: str):
    url = API_URL.format(phone_number)
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("status") == "success" and data.get("result"):
            return data["result"]
        return None
    except Exception as e:
        return {"error": str(e)}

# === ADMIN DECORATOR ===
def admin_required(func):
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = str(update.effective_user.id)
        if user_id != ADMIN_CHAT_ID and not admin_authenticated.get(user_id):
            await update.message.reply_text(
                f"🔒 *Admin access required.*\nSend `/admin {ADMIN_PASSWORD}`\n\n"
                f"👑 Owner: {OWNER_NAME} ({OWNER_USERNAME})",
                parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# === ADMIN COMMANDS ===
@admin_required
async def admin_panel(update: Update, context: CallbackContext):
    """Show admin panel with all commands (called after login)"""
    keyboard = [
        [InlineKeyboardButton("📊 Quick Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📅 Daily Analytics", callback_data="admin_daily")],
        [InlineKeyboardButton("📆 Monthly Analytics", callback_data="admin_monthly")],
        [InlineKeyboardButton("🏆 Lifetime Analytics", callback_data="admin_lifetime")],
        [InlineKeyboardButton("👤 User Stats", callback_data="admin_userstats")],
        [InlineKeyboardButton("🏅 Top Users", callback_data="admin_top")],
        [InlineKeyboardButton("🔄 Reset User Limit", callback_data="admin_reset")],
        [InlineKeyboardButton("⚙️ Set Custom Limit", callback_data="admin_setlimit")],
        [InlineKeyboardButton("🔒 Logout", callback_data="admin_logout")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👑 *Admin Panel*\n\n"
        f"Welcome {OWNER_NAME}!\n\n"
        f"📊 *Total Users:* {len(user_data_store)}\n"
        f"🔍 *Total Searches:* {admin_analytics['lifetime']['total_searches']}\n"
        f"⚙️ *Default Limit:* {MAX_SEARCHES_PER_USER} per {RESET_HOURS}h\n\n"
        f"Use the buttons below or type commands directly:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

@admin_required
async def daily_stats(update: Update, context: CallbackContext):
    today = datetime.now().strftime("%Y-%m-%d")
    stats = admin_analytics["daily"].get(today, {"count": 0, "users": set()})
    active_users = len(stats["users"])
    
    message = f"📅 *Daily Statistics* – {today}\n\n"
    message += f"🔍 Total searches today: `{stats['count']}`\n"
    message += f"👥 Active users today: `{active_users}`\n"
    message += f"📊 Per user limit: `{MAX_SEARCHES_PER_USER}` searches\n"
    message += f"⏰ Reset every: `{RESET_HOURS}` hours"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@admin_required
async def monthly_stats(update: Update, context: CallbackContext):
    current_month = datetime.now().strftime("%Y-%m")
    stats = admin_analytics["monthly"].get(current_month, {"count": 0, "users": set()})
    active_users = len(stats["users"])
    
    message = f"📆 *Monthly Statistics* – {current_month}\n\n"
    message += f"🔍 Total searches this month: `{stats['count']}`\n"
    message += f"👥 Active users this month: `{active_users}`\n"
    message += f"📊 Per user limit: `{MAX_SEARCHES_PER_USER}` searches"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@admin_required
async def lifetime_stats(update: Update, context: CallbackContext):
    total_users = admin_analytics["lifetime"]["total_users"]
    total_searches = admin_analytics["lifetime"]["total_searches"]
    avg_searches_per_user = total_searches / total_users if total_users > 0 else 0
    
    message = f"🏆 *Lifetime Statistics*\n\n"
    message += f"👥 Total users: `{total_users}`\n"
    message += f"🔍 Total searches: `{total_searches}`\n"
    message += f"📊 Avg searches/user: `{avg_searches_per_user:.1f}`\n"
    message += f"⚙️ Limit per user: `{MAX_SEARCHES_PER_USER}`\n"
    message += f"🔄 Reset hours: `{RESET_HOURS}`"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@admin_required
async def quick_stats(update: Update, context: CallbackContext):
    total_users = len(user_data_store)
    total_searches = admin_analytics["lifetime"]["total_searches"]
    today_searches = admin_analytics["daily"].get(datetime.now().strftime("%Y-%m-%d"), {"count": 0})["count"]
    
    message = f"📊 *Quick Statistics*\n\n"
    message += f"👥 Total users: `{total_users}`\n"
    message += f"🔍 Total searches: `{total_searches}`\n"
    message += f"📅 Today's searches: `{today_searches}`\n"
    message += f"⚙️ Limit per user: `{MAX_SEARCHES_PER_USER}`"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@admin_required
async def user_stats(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Usage: `/user_stats <user_id>`\n\nExample: `/user_stats 8481566006`", parse_mode="Markdown")
        return
    
    target_user = args[0]
    if target_user not in user_data_store:
        await update.message.reply_text(f"❌ User `{target_user}` not found", parse_mode="Markdown")
        return
    
    user_data = user_data_store[target_user]
    remaining = get_user_remaining(target_user)
    reset_left = get_reset_time_left(target_user)
    
    message = f"👤 *User Statistics* – `{target_user}`\n\n"
    message += f"🔍 Remaining searches: `{remaining}/{MAX_SEARCHES_PER_USER}`\n"
    message += f"✅ Total searches ever: `{user_data['total_searches']}`\n"
    message += f"⏰ Reset in: `{reset_left}`\n"
    message += f"📅 First seen: `{user_data['first_seen'].strftime('%Y-%m-%d %H:%M')}`\n"
    last_search = user_data['search_history'][-1].strftime('%Y-%m-%d %H:%M') if user_data['search_history'] else 'Never'
    message += f"🕒 Last search: `{last_search}`"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@admin_required
async def top_users(update: Update, context: CallbackContext):
    if not user_data_store:
        await update.message.reply_text("No users yet.")
        return
    
    sorted_users = sorted(user_data_store.items(), key=lambda x: x[1]["total_searches"], reverse=True)[:10]
    
    message = f"🏅 *Top 10 Users (by total searches)*\n\n"
    for idx, (uid, data) in enumerate(sorted_users, 1):
        short_id = uid[:8] + "..." if len(uid) > 8 else uid
        message += f"{idx}. `{short_id}` – {data['total_searches']} searches\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@admin_required
async def reset_user_limit(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Usage: `/reset_limit <user_id>`\n\nExample: `/reset_limit 8481566006`", parse_mode="Markdown")
        return
    
    target_user = args[0]
    if target_user in user_data_store:
        now = datetime.now()
        user_data_store[target_user]["remaining"] = MAX_SEARCHES_PER_USER
        user_data_store[target_user]["reset_time"] = now + timedelta(hours=RESET_HOURS)
        await update.message.reply_text(f"✅ Limit reset to {MAX_SEARCHES_PER_USER} for user `{target_user}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ User `{target_user}` not found. They need to search at least once first.", parse_mode="Markdown")

@admin_required
async def set_limit(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ Usage: `/set_limit <user_id> <new_limit>`\n\nExample: `/set_limit 8481566006 10`", parse_mode="Markdown")
        return
    
    target_user = args[0]
    try:
        new_limit = int(args[1])
        if target_user in user_data_store:
            user_data_store[target_user]["remaining"] = new_limit
        else:
            now = datetime.now()
            user_data_store[target_user] = {
                "remaining": new_limit,
                "reset_time": now + timedelta(hours=RESET_HOURS),
                "search_history": [],
                "total_searches": 0,
                "first_seen": now
            }
            admin_analytics["lifetime"]["total_users"] = len(user_data_store)
        await update.message.reply_text(f"✅ Limit set to `{new_limit}` for user `{target_user}`", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Invalid limit value. Use a number.")

@admin_required
async def broadcast(update: Update, context: CallbackContext):
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("❌ Usage: `/broadcast <your message>`")
        return
    await update.message.reply_text(f"📢 Broadcast sent (simulated):\n\n{message}")

# === USER COMMANDS ===
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = str(user.id)
    remaining = get_user_remaining(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
        [InlineKeyboardButton("📊 My Limit", callback_data="mylimit")],
        [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")]
    ]
    
    await update.message.reply_text(
        f"📞 *Number Info Bot*\n\n"
        f"👋 Hello {user.first_name}!\n\n"
        f"🔍 *Send a phone number* (10+ digits) to get information.\n\n"
        f"📊 *Your remaining searches:* {remaining}/{MAX_SEARCHES_PER_USER}\n"
        f"⏰ Resets in: {get_reset_time_left(user_id)}\n\n"
        f"✅ Each number search consumes 1 limit.\n"
        f"🔄 Limit resets every {RESET_HOURS} hours.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_login(update: Update, context: CallbackContext):
    """Handle admin login with password"""
    user_id = str(update.effective_user.id)
    args = context.args
    
    if len(args) != 1:
        await update.message.reply_text(
            "❌ *Admin Login*\n\nUsage: `/admin Sold@9819`\n\n"
            f"👑 Owner: {OWNER_NAME} ({OWNER_USERNAME})",
            parse_mode="Markdown"
        )
        return
    
    if args[0] == ADMIN_PASSWORD:
        admin_authenticated[user_id] = True
        
        # Show admin panel after successful login
        keyboard = [
            [InlineKeyboardButton("📊 Quick Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("📅 Daily Analytics", callback_data="admin_daily")],
            [InlineKeyboardButton("📆 Monthly Analytics", callback_data="admin_monthly")],
            [InlineKeyboardButton("🏆 Lifetime Analytics", callback_data="admin_lifetime")],
            [InlineKeyboardButton("👤 User Stats", callback_data="admin_userstats")],
            [InlineKeyboardButton("🏅 Top Users", callback_data="admin_top")],
            [InlineKeyboardButton("🔄 Reset User Limit", callback_data="admin_reset")],
            [InlineKeyboardButton("⚙️ Set Custom Limit", callback_data="admin_setlimit")],
            [InlineKeyboardButton("🔒 Logout", callback_data="admin_logout")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *Admin access granted!*\n\n"
            f"👑 Welcome {OWNER_NAME}\n\n"
            f"📊 *Bot Status:*\n"
            f"• Total Users: `{len(user_data_store)}`\n"
            f"• Total Searches: `{admin_analytics['lifetime']['total_searches']}`\n"
            f"• Default Limit: `{MAX_SEARCHES_PER_USER}` searches per {RESET_HOURS}h\n\n"
            f"📋 *Admin Panel:*\n"
            f"Use the buttons below or type commands directly.\n\n"
            f"📌 *Commands:*\n"
            f"`/daily` – Today's stats\n"
            f"`/monthly` – Monthly stats\n"
            f"`/lifetime` – Lifetime stats\n"
            f"`/stats` – Quick stats\n"
            f"`/user_stats <id>` – Specific user\n"
            f"`/top` – Top 10 users\n"
            f"`/reset_limit <id>` – Reset to 5\n"
            f"`/set_limit <id> <num>` – Custom limit\n"
            f"`/logout` – End session",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "❌ *Incorrect password!*\n\n"
            "Access denied.\n"
            f"👑 Owner: {OWNER_NAME}",
            parse_mode="Markdown"
        )

async def admin_logout(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id in admin_authenticated:
        del admin_authenticated[user_id]
        await update.message.reply_text("🔒 *Admin session ended.*\n\nUse `/admin {ADMIN_PASSWORD}` to login again.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ You are not logged in as admin.")

async def handle_number(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_input = update.message.text.strip()
    phone_number = ''.join(filter(str.isdigit, user_input))
    
    if len(phone_number) < 10:
        await update.message.reply_text("❌ Send a valid 10+ digit number.")
        return
    
    remaining = get_user_remaining(user_id)
    if remaining <= 0:
        reset_time_left = get_reset_time_left(user_id)
        await update.message.reply_text(
            f"⚠️ *Limit Exceeded!*\n\n"
            f"You have used all {MAX_SEARCHES_PER_USER} searches.\n"
            f"⏰ Resets in: {reset_time_left}\n\n"
            f"📢 Join channel: {CHANNEL_ID}",
            parse_mode="Markdown"
        )
        return
    
    await update.message.chat.send_action(action="typing")
    info = get_number_info(phone_number)
    
    if not info or (isinstance(info, dict) and "error" in info):
        await update.message.reply_text("⚠️ No information found for this number.")
        return
    
    decrement_user_search(user_id)
    new_remaining = get_user_remaining(user_id)
    
    record = info[0] if isinstance(info, list) and info else info
    
    message = f"🔍 *Results for {phone_number}*\n\n"
    message += f"👤 Name: {record.get('name', 'N/A')}\n"
    message += f"📱 Number: {record.get('num', phone_number)}\n"
    message += f"🆔 Aadhar: {record.get('aadhar', 'N/A')}\n"
    message += f"📍 Address: {record.get('address', 'N/A')}\n"
    message += f"📧 Email: {record.get('email', 'N/A')}\n\n"
    message += f"📊 *Remaining:* {new_remaining}/{MAX_SEARCHES_PER_USER}\n"
    message += f"⏰ Resets in: {get_reset_time_left(user_id)}"
    
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID)],
        [InlineKeyboardButton("📊 My Limit", callback_data="mylimit")],
        [InlineKeyboardButton("🔄 New Search", callback_data="new")]
    ]
    
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    # Admin button callbacks
    if query.data == "admin_stats":
        total_users = len(user_data_store)
        total_searches = admin_analytics["lifetime"]["total_searches"]
        today_searches = admin_analytics["daily"].get(datetime.now().strftime("%Y-%m-%d"), {"count": 0})["count"]
        await query.message.reply_text(
            f"📊 *Quick Stats*\n\n👥 Users: {total_users}\n🔍 Searches: {total_searches}\n📅 Today: {today_searches}",
            parse_mode="Markdown"
        )
    elif query.data == "admin_daily":
        today = datetime.now().strftime("%Y-%m-%d")
        stats = admin_analytics["daily"].get(today, {"count": 0, "users": set()})
        await query.message.reply_text(f"📅 *Daily* – {today}\n🔍 Searches: {stats['count']}\n👥 Users: {len(stats['users'])}", parse_mode="Markdown")
    elif query.data == "admin_monthly":
        month = datetime.now().strftime("%Y-%m")
        stats = admin_analytics["monthly"].get(month, {"count": 0, "users": set()})
        await query.message.reply_text(f"📆 *Monthly* – {month}\n🔍 Searches: {stats['count']}\n👥 Users: {len(stats['users'])}", parse_mode="Markdown")
    elif query.data == "admin_lifetime":
        await lifetime_stats(update, context)
    elif query.data == "admin_top":
        await top_users(update, context)
    elif query.data == "admin_logout":
        if user_id in admin_authenticated:
            del admin_authenticated[user_id]
            await query.message.reply_text("🔒 Logged out.")
    elif query.data == "admin_userstats":
        await query.message.reply_text("Send `/user_stats <user_id>`\nExample: `/user_stats 8481566006`")
    elif query.data == "admin_reset":
        await query.message.reply_text("Send `/reset_limit <user_id>`\nExample: `/reset_limit 8481566006`")
    elif query.data == "admin_setlimit":
        await query.message.reply_text("Send `/set_limit <user_id> <limit>`\nExample: `/set_limit 8481566006 10`")
    
    # User button callbacks
    elif query.data == "new":
        await query.message.reply_text("Send another phone number:")
    elif query.data == "mylimit":
        remaining = get_user_remaining(user_id)
        reset_time = get_reset_time_left(user_id)
        user_data = get_user_data(user_id)
        await query.message.reply_text(
            f"📊 *Your Limit*\n\n🔍 Remaining: {remaining}/{MAX_SEARCHES_PER_USER}\n✅ Total: {user_data['total_searches']}\n⏰ Resets in: {reset_time}",
            parse_mode="Markdown"
        )
    elif query.data == "about":
        await query.message.reply_text(f"🤖 *Number Info Bot*\n\n👑 Owner: {OWNER_NAME}\n📢 Channel: {CHANNEL_ID}\n🔒 Limit: {MAX_SEARCHES_PER_USER}/24h")

async def unknown(update: Update, context: CallbackContext):
    await update.message.reply_text("❓ Send a phone number (digits only) or `/admin` to login.", parse_mode="Markdown")

# === MAIN ===
def main():
    Thread(target=run_flask).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("logout", admin_logout))
    
    # Admin commands
    app.add_handler(CommandHandler("stats", quick_stats))
    app.add_handler(CommandHandler("daily", daily_stats))
    app.add_handler(CommandHandler("monthly", monthly_stats))
    app.add_handler(CommandHandler("lifetime", lifetime_stats))
    app.add_handler(CommandHandler("user_stats", user_stats))
    app.add_handler(CommandHandler("top", top_users))
    app.add_handler(CommandHandler("reset_limit", reset_user_limit))
    app.add_handler(CommandHandler("set_limit", set_limit))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot started with working admin login and full menu!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, timeout=30)

if __name__ == "__main__":
    main()
