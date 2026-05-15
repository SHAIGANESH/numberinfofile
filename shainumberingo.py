import requests
import json
import asyncio
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

# === PAYMENT CONFIGURATION ===
UPI_ID = "shaiganesh@slc"
ACCOUNT_HOLDER = "Shailesh Kumar"
PRICE_PER_SEARCH = 1  # ₹1 per search
FREE_SEARCHES = 3     # 3 free searches per user

# === SEARCH CONFIGURATION ===
AUTO_DELETE_SECONDS = 30  # Auto-delete results after 30 seconds

# Store user data
user_data_store = {}

# Store pending payment approvals
pending_payments = {}

# Admin analytics
admin_analytics = {
    "daily": {},
    "monthly": {},
    "lifetime": {"total_searches": 0, "total_users": 0, "total_paid": 0}
}

admin_authenticated = {}

# === HELPER FUNCTIONS ===
def get_user_data(user_id: str):
    """Get or create user data"""
    now = datetime.now()
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "free_searches_used": 0,
            "paid_searches": 0,
            "total_searches": 0,
            "search_history": [],
            "first_seen": now,
            "last_seen": now
        }
        admin_analytics["lifetime"]["total_users"] = len(user_data_store)
    return user_data_store[user_id]

def get_remaining_free(user_id: str):
    """Get remaining free searches"""
    user_data = get_user_data(user_id)
    remaining = FREE_SEARCHES - user_data["free_searches_used"]
    return max(0, remaining)

def get_remaining_paid(user_id: str):
    """Get remaining paid searches"""
    user_data = get_user_data(user_id)
    return user_data["paid_searches"]

def can_search(user_id: str):
    """Check if user can search (free or paid)"""
    return get_remaining_free(user_id) > 0 or get_remaining_paid(user_id) > 0

def use_search(user_id: str):
    """Use one search (free first, then paid)"""
    user_data = get_user_data(user_id)
    now = datetime.now()
    
    if get_remaining_free(user_id) > 0:
        user_data["free_searches_used"] += 1
        search_type = "free"
    elif get_remaining_paid(user_id) > 0:
        user_data["paid_searches"] -= 1
        search_type = "paid"
        admin_analytics["lifetime"]["total_paid"] += 1
    else:
        return False, None
    
    user_data["total_searches"] += 1
    user_data["search_history"].append(now)
    user_data["last_seen"] = now
    
    admin_analytics["lifetime"]["total_searches"] += 1
    
    # Daily analytics
    date_key = now.strftime("%Y-%m-%d")
    if date_key not in admin_analytics["daily"]:
        admin_analytics["daily"][date_key] = {"count": 0, "users": set(), "paid": 0}
    admin_analytics["daily"][date_key]["count"] += 1
    admin_analytics["daily"][date_key]["users"].add(user_id)
    if search_type == "paid":
        admin_analytics["daily"][date_key]["paid"] += 1
    
    # Monthly analytics
    month_key = now.strftime("%Y-%m")
    if month_key not in admin_analytics["monthly"]:
        admin_analytics["monthly"][month_key] = {"count": 0, "users": set(), "paid": 0}
    admin_analytics["monthly"][month_key]["count"] += 1
    admin_analytics["monthly"][month_key]["users"].add(user_id)
    if search_type == "paid":
        admin_analytics["monthly"][month_key]["paid"] += 1
    
    return True, search_type

def add_paid_searches(user_id: str, amount: int):
    """Add paid searches (₹1 = 1 search)"""
    user_data = get_user_data(user_id)
    searches_to_add = amount  # ₹1 = 1 search
    user_data["paid_searches"] += searches_to_add
    return searches_to_add

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

async def delete_message_after_delay(context: CallbackContext, chat_id: int, message_id: int, delay: int):
    """Delete message after specified seconds"""
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

# === PAYMENT QR GENERATION ===
def get_payment_keyboard(amount: int = 1):
    """Generate payment keyboard with QR and UPI details"""
    upi_string = f"upi://pay?pa={UPI_ID}&pn={ACCOUNT_HOLDER}&am={amount}&cu=INR"
    
    keyboard = [
        [InlineKeyboardButton("💳 Pay ₹1 (1 Search)", url=upi_string)],
        [InlineKeyboardButton("💳 Pay ₹5 (5 Searches)", url=f"upi://pay?pa={UPI_ID}&pn={ACCOUNT_HOLDER}&am=5&cu=INR")],
        [InlineKeyboardButton("💳 Pay ₹10 (10 Searches)", url=f"upi://pay?pa={UPI_ID}&pn={ACCOUNT_HOLDER}&am=10&cu=INR")],
        [InlineKeyboardButton("✅ I Have Paid", callback_data="confirm_payment")],
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID)]
    ]
    return InlineKeyboardMarkup(keyboard)

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

# === HELP COMMAND ===
async def help_command(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    remaining_free = get_remaining_free(user_id)
    remaining_paid = get_remaining_paid(user_id)
    
    help_text = f"""
🤖 *Number Info Bot - Help Guide*

━━━━━━━━━━━━━━━━━━━━
📌 *BASIC COMMANDS*
━━━━━━━━━━━━━━━━━━━━

/start - Start the bot
/help - Show this help menu
/num <number> - Search for number info
/mylimit - Check your remaining searches
/buy - Buy more searches (₹1 per search)

━━━━━━━━━━━━━━━━━━━━
💰 *SEARCH LIMITS*
━━━━━━━━━━━━━━━━━━━━

🎁 *Free Searches:* {remaining_free}/{FREE_SEARCHES}
💎 *Paid Searches:* {remaining_paid}
💵 *Price:* ₹{PRICE_PER_SEARCH} per search

━━━━━━━━━━━━━━━━━━━━
📝 *HOW TO USE*
━━━━━━━━━━━━━━━━━━━━

1️⃣ Send any 10-digit number
2️⃣ Or use `/num 9876543210`
3️⃣ Get instant results
4️⃣ Results auto-delete in {AUTO_DELETE_SECONDS} seconds

━━━━━━━━━━━━━━━━━━━━
🛒 *BUY MORE SEARCHES*
━━━━━━━━━━━━━━━━━━━━

Use /buy to get payment QR
Pay via UPI: `{UPI_ID}`
After payment, click "I Have Paid"

━━━━━━━━━━━━━━━━━━━━
📢 *SUPPORT*
━━━━━━━━━━━━━━━━━━━━

📢 Channel: {CHANNEL_ID}
👑 Owner: {OWNER_USERNAME}

For issues, contact owner after payment.
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

# === USER COMMANDS ===
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = str(user.id)
    remaining_free = get_remaining_free(user_id)
    remaining_paid = get_remaining_paid(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
        [InlineKeyboardButton("💰 Buy Searches", callback_data="buy")],
        [InlineKeyboardButton("📊 My Limit", callback_data="mylimit")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    
    await update.message.reply_text(
        f"📞 *Number Info Bot*\n\n"
        f"👋 Hello {user.first_name}!\n\n"
        f"🔍 *Send a phone number* (10+ digits) to get information.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Your Balance*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Free searches left: `{remaining_free}/{FREE_SEARCHES}`\n"
        f"💎 Paid searches left: `{remaining_paid}`\n"
        f"💵 Price: ₹{PRICE_PER_SEARCH}/search\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 Use `/buy` to purchase more searches\n"
        f"📌 Use `/help` for full guide\n\n"
        f"⚡ *Results auto-delete in {AUTO_DELETE_SECONDS} seconds*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def mylimit(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    remaining_free = get_remaining_free(user_id)
    remaining_paid = get_remaining_paid(user_id)
    user_data = get_user_data(user_id)
    
    await update.message.reply_text(
        f"📊 *Your Search Limit*\n\n"
        f"🎁 Free searches: `{remaining_free}/{FREE_SEASRES}`\n"
        f"💎 Paid searches: `{remaining_paid}`\n"
        f"✅ Total searches done: `{user_data['total_searches']}`\n"
        f"💵 Price per search: ₹{PRICE_PER_SEARCH}\n\n"
        f"Use `/buy` to add more searches.",
        parse_mode="Markdown"
    )

async def buy_searches(update: Update, context: CallbackContext):
    """Show payment QR and UPI details"""
    user_id = str(update.effective_user.id)
    
    message = f"""
💰 *Purchase More Searches*

━━━━━━━━━━━━━━━━━━━━
💳 *UPI Payment Details*
━━━━━━━━━━━━━━━━━━━━

👤 Account Holder: `{ACCOUNT_HOLDER}`
📱 UPI ID: `{UPI_ID}`
💵 Price: ₹{PRICE_PER_SEARCH} per search

━━━━━━━━━━━━━━━━━━━━
📝 *INSTRUCTIONS*
━━━━━━━━━━━━━━━━━━━━

1️⃣ Click any payment button below
2️⃣ Pay using Google Pay / PhonePe / any UPI app
3️⃣ After payment, click "✅ I Have Paid"
4️⃣ Admin will verify and add searches

━━━━━━━━━━━━━━━━━━━━
🎁 *BONUS*
━━━━━━━━━━━━━━━━━━━━

• Pay ₹10 → Get 10 + 1 FREE = 11 searches
• Pay ₹20 → Get 20 + 3 FREE = 23 searches

━━━━━━━━━━━━━━━━━━━━

💬 *After payment, send screenshot to owner*
👑 Owner: {OWNER_USERNAME}
"""
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=get_payment_keyboard())

async def num_command(update: Update, context: CallbackContext):
    """Handle /num <number> command"""
    user_id = str(update.effective_user.id)
    args = context.args
    
    if len(args) != 1:
        await update.message.reply_text("❌ Usage: `/num 9876543210`\n\nSend a 10+ digit number.", parse_mode="Markdown")
        return
    
    phone_number = ''.join(filter(str.isdigit, args[0]))
    if len(phone_number) < 10:
        await update.message.reply_text("❌ Please send a valid 10+ digit number.")
        return
    
    # Process search
    await process_number_search(update, context, phone_number, user_id)

async def process_number_search(update: Update, context: CallbackContext, phone_number: str, user_id: str):
    """Process number search with limit checking"""
    
    # Check if user can search
    if not can_search(user_id):
        remaining_free = get_remaining_free(user_id)
        await update.message.reply_text(
            f"⚠️ *No Searches Left!*\n\n"
            f"🎁 Free searches used: {FREE_SEARCHES - remaining_free}/{FREE_SEARCHES}\n"
            f"💎 Paid searches: 0\n\n"
            f"💵 Buy more searches: ₹{PRICE_PER_SEARCH} each\n\n"
            f"👉 Use `/buy` to purchase",
            parse_mode="Markdown"
        )
        return
    
    # Send typing indicator
    await update.message.chat.send_action(action="typing")
    
    # Get number info
    info = get_number_info(phone_number)
    
    if not info or (isinstance(info, dict) and "error" in info):
        await update.message.reply_text("⚠️ No information found for this number.")
        return
    
    # Use one search
    success, search_type = use_search(user_id)
    if not success:
        await update.message.reply_text("❌ Failed to process search. Please try again.")
        return
    
    # Get updated balances
    remaining_free = get_remaining_free(user_id)
    remaining_paid = get_remaining_paid(user_id)
    
    record = info[0] if isinstance(info, list) and info else info
    
    result_message = f"""
🔍 *Number Search Result*

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
💰 *Balance Update*
━━━━━━━━━━━━━━━━━━━━

🎁 Free left: `{remaining_free}/{FREE_SEARCHES}`
💎 Paid left: `{remaining_paid}`
💵 Search type: `{search_type.upper()}`

━━━━━━━━━━━━━━━━━━━━
⚡ *This message will auto-delete in {AUTO_DELETE_SECONDS} seconds*
    """
    
    msg = await update.message.reply_text(result_message, parse_mode="Markdown")
    
    # Auto-delete after 30 seconds
    asyncio.create_task(delete_message_after_delay(context, msg.chat_id, msg.message_id, AUTO_DELETE_SECONDS))
    
    # Also delete user's original message
    if update.message:
        asyncio.create_task(delete_message_after_delay(context, update.message.chat_id, update.message.message_id, AUTO_DELETE_SECONDS))

async def handle_number(update: Update, context: CallbackContext):
    """Handle direct number input"""
    user_id = str(update.effective_user.id)
    user_input = update.message.text.strip()
    phone_number = ''.join(filter(str.isdigit, user_input))
    
    if len(phone_number) < 10:
        await update.message.reply_text("❌ Send a valid 10+ digit number.\n\nExample: `9876543210`", parse_mode="Markdown")
        return
    
    await process_number_search(update, context, phone_number, user_id)

# === ADMIN COMMANDS ===
async def admin_login(update: Update, context: CallbackContext):
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
        
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("📅 Daily", callback_data="admin_daily")],
            [InlineKeyboardButton("📆 Monthly", callback_data="admin_monthly")],
            [InlineKeyboardButton("🏆 Lifetime", callback_data="admin_lifetime")],
            [InlineKeyboardButton("💰 Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("👤 User Info", callback_data="admin_userinfo")],
            [InlineKeyboardButton("➕ Add Searches", callback_data="admin_add")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔒 Logout", callback_data="admin_logout")]
        ]
        
        await update.message.reply_text(
            f"✅ *Admin Access Granted!*\n\n"
            f"👑 Welcome {OWNER_NAME}\n\n"
            f"📊 *Bot Status*\n"
            f"• Users: `{len(user_data_store)}`\n"
            f"• Total Searches: `{admin_analytics['lifetime']['total_searches']}`\n"
            f"• Paid Searches: `{admin_analytics['lifetime']['total_paid']}`\n"
            f"• Free Limit: `{FREE_SEARCHES}`/user\n"
            f"• Price: ₹{PRICE_PER_SEARCH}/search\n\n"
            f"📋 *Admin Commands*\n"
            f"`/stats` - Quick stats\n"
            f"`/daily` - Daily analytics\n"
            f"`/monthly` - Monthly analytics\n"
            f"`/lifetime` - Lifetime stats\n"
            f"`/payments` - Payment history\n"
            f"`/userinfo <id>` - User details\n"
            f"`/add <id> <amount>` - Add paid searches\n"
            f"`/broadcast <msg>` - Send message\n"
            f"`/logout` - End session",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("❌ *Incorrect password!*", parse_mode="Markdown")

async def admin_logout(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id in admin_authenticated:
        del admin_authenticated[user_id]
        await update.message.reply_text("🔒 *Admin session ended.*", parse_mode="Markdown")

@admin_required
async def admin_stats(update: Update, context: CallbackContext):
    total_users = len(user_data_store)
    total_searches = admin_analytics["lifetime"]["total_searches"]
    total_paid = admin_analytics["lifetime"]["total_paid"]
    today = datetime.now().strftime("%Y-%m-%d")
    today_stats = admin_analytics["daily"].get(today, {"count": 0, "paid": 0})
    
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"🔍 Total Searches: `{total_searches}`\n"
        f"💰 Paid Searches: `{total_paid}`\n"
        f"💵 Revenue: ₹{total_paid}\n\n"
        f"📅 Today: `{today_stats['count']}` searches\n"
        f"💸 Today Paid: `{today_stats['paid']}` (₹{today_stats['paid']})\n\n"
        f"🎁 Free per user: `{FREE_SEARCHES}`\n"
        f"💵 Price: ₹{PRICE_PER_SEARCH}/search",
        parse_mode="Markdown"
    )

@admin_required
async def admin_daily(update: Update, context: CallbackContext):
    today = datetime.now().strftime("%Y-%m-%d")
    stats = admin_analytics["daily"].get(today, {"count": 0, "users": set(), "paid": 0})
    
    await update.message.reply_text(
        f"📅 *Daily Report* – {today}\n\n"
        f"🔍 Total Searches: `{stats['count']}`\n"
        f"💰 Paid Searches: `{stats['paid']}`\n"
        f"💵 Revenue: ₹{stats['paid']}\n"
        f"👥 Active Users: `{len(stats['users'])}`",
        parse_mode="Markdown"
    )

@admin_required
async def admin_monthly(update: Update, context: CallbackContext):
    month = datetime.now().strftime("%Y-%m")
    stats = admin_analytics["monthly"].get(month, {"count": 0, "users": set(), "paid": 0})
    
    await update.message.reply_text(
        f"📆 *Monthly Report* – {month}\n\n"
        f"🔍 Total Searches: `{stats['count']}`\n"
        f"💰 Paid Searches: `{stats['paid']}`\n"
        f"💵 Revenue: ₹{stats['paid']}\n"
        f"👥 Active Users: `{len(stats['users'])}`",
        parse_mode="Markdown"
    )

@admin_required
async def admin_lifetime(update: Update, context: CallbackContext):
    await update.message.reply_text(
        f"🏆 *Lifetime Statistics*\n\n"
        f"👥 Total Users: `{admin_analytics['lifetime']['total_users']}`\n"
        f"🔍 Total Searches: `{admin_analytics['lifetime']['total_searches']}`\n"
        f"💰 Total Paid: `{admin_analytics['lifetime']['total_paid']}`\n"
        f"💵 Total Revenue: ₹{admin_analytics['lifetime']['total_paid']}\n"
        f"🎁 Free Limit: `{FREE_SEARCHES}`/user\n"
        f"💵 Price: ₹{PRICE_PER_SEARCH}/search",
        parse_mode="Markdown"
    )

@admin_required
async def admin_payments(update: Update, context: CallbackContext):
    await update.message.reply_text(
        f"💰 *Payment Management*\n\n"
        f"💵 Price: ₹{PRICE_PER_SEARCH} per search\n"
        f"💳 UPI ID: `{UPI_ID}`\n"
        f"👤 Account: `{ACCOUNT_HOLDER}`\n\n"
        f"📌 *To add searches to a user:*\n"
        f"`/add <user_id> <amount_rupees>`\n\n"
        f"📌 *Example:*\n"
        f"`/add 8481566006 10`\n\n"
        f"💰 Total Revenue: ₹{admin_analytics['lifetime']['total_paid']}",
        parse_mode="Markdown"
    )

@admin_required
async def admin_userinfo(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Usage: `/userinfo <user_id>`\n\nExample: `/userinfo 8481566006`", parse_mode="Markdown")
        return
    
    target_user = args[0]
    if target_user not in user_data_store:
        await update.message.reply_text(f"❌ User `{target_user}` not found", parse_mode="Markdown")
        return
    
    user_data = user_data_store[target_user]
    remaining_free = FREE_SEARCHES - user_data["free_searches_used"]
    remaining_free = max(0, remaining_free)
    
    await update.message.reply_text(
        f"👤 *User Info* – `{target_user}`\n\n"
        f"🎁 Free used: `{user_data['free_searches_used']}/{FREE_SEARCHES}`\n"
        f"💎 Paid remaining: `{user_data['paid_searches']}`\n"
        f"✅ Total searches: `{user_data['total_searches']}`\n"
        f"📅 First seen: `{user_data['first_seen'].strftime('%Y-%m-%d %H:%M')}`\n"
        f"🕒 Last seen: `{user_data['last_seen'].strftime('%Y-%m-%d %H:%M')}`\n\n"
        f"📌 *To add searches:* `/add {target_user} <amount>`",
        parse_mode="Markdown"
    )

@admin_required
async def admin_add(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ Usage: `/add <user_id> <amount_rupees>`\n\nExample: `/add 8481566006 10`\n(₹10 = 10 searches)", parse_mode="Markdown")
        return
    
    target_user = args[0]
    try:
        amount = int(args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive")
            return
        
        searches_added = add_paid_searches(target_user, amount)
        await update.message.reply_text(
            f"✅ Added `{searches_added}` searches to user `{target_user}`\n\n"
            f"💰 Amount: ₹{amount}\n"
            f"🔍 Searches: {searches_added}\n"
            f"💵 Total paid revenue: ₹{admin_analytics['lifetime']['total_paid']}",
            parse_mode="Markdown"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user,
                text=f"✅ *Searches Added!*\n\n"
                     f"🔍 `{searches_added}` searches added to your account.\n"
                     f"💵 Use `/mylimit` to check balance.",
                parse_mode="Markdown"
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Use a number.")

@admin_required
async def admin_broadcast(update: Update, context: CallbackContext):
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("❌ Usage: `/broadcast <message>`")
        return
    
    success_count = 0
    fail_count = 0
    
    for user_id in user_data_store.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Announcement*\n\n{message}",
                parse_mode="Markdown"
            )
            success_count += 1
        except:
            fail_count += 1
    
    await update.message.reply_text(
        f"📢 *Broadcast Sent*\n\n"
        f"✅ Success: `{success_count}`\n"
        f"❌ Failed: `{fail_count}`",
        parse_mode="Markdown"
    )

@admin_required
async def admin_commands(update: Update, context: CallbackContext):
    """Show all admin commands"""
    await update.message.reply_text(
        f"👑 *Admin Commands List*\n\n"
        f"📊 `/stats` - Quick statistics\n"
        f"📅 `/daily` - Daily report\n"
        f"📆 `/monthly` - Monthly report\n"
        f"🏆 `/lifetime` - Lifetime stats\n"
        f"💰 `/payments` - Payment info\n"
        f"👤 `/userinfo <id>` - User details\n"
        f"➕ `/add <id> <amount>` - Add paid searches\n"
        f"📢 `/broadcast <msg>` - Send to all\n"
        f"🔒 `/logout` - End session\n\n"
        f"💵 Price: ₹{PRICE_PER_SEARCH}/search\n"
        f"🎁 Free: {FREE_SEARCHES}/user",
        parse_mode="Markdown"
    )

# === BUTTON CALLBACKS ===
async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    # Admin buttons
    if query.data == "admin_stats":
        await admin_stats(update, context)
    elif query.data == "admin_daily":
        await admin_daily(update, context)
    elif query.data == "admin_monthly":
        await admin_monthly(update, context)
    elif query.data == "admin_lifetime":
        await admin_lifetime(update, context)
    elif query.data == "admin_payments":
        await admin_payments(update, context)
    elif query.data == "admin_userinfo":
        await query.message.reply_text("Send `/userinfo <user_id>`\nExample: `/userinfo 8481566006`")
    elif query.data == "admin_add":
        await query.message.reply_text("Send `/add <user_id> <amount>`\nExample: `/add 8481566006 10`")
    elif query.data == "admin_broadcast":
        await query.message.reply_text("Send `/broadcast <your message>`")
    elif query.data == "admin_logout":
        if user_id in admin_authenticated:
            del admin_authenticated[user_id]
            await query.message.reply_text("🔒 Logged out.")
    
    # User buttons
    elif query.data == "buy":
        await buy_searches(update, context)
    elif query.data == "mylimit":
        remaining_free = get_remaining_free(user_id)
        remaining_paid = get_remaining_paid(user_id)
        user_data = get_user_data(user_id)
        await query.message.reply_text(
            f"📊 *Your Balance*\n\n"
            f"🎁 Free left: `{remaining_free}/{FREE_SEARCHES}`\n"
            f"💎 Paid left: `{remaining_paid}`\n"
            f"✅ Total used: `{user_data['total_searches']}`\n"
            f"💵 Price: ₹{PRICE_PER_SEARCH}/search",
            parse_mode="Markdown"
        )
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "confirm_payment":
        await query.message.reply_text(
            f"✅ *Payment Confirmation*\n\n"
            f"1️⃣ Send screenshot of payment to {OWNER_USERNAME}\n"
            f"2️⃣ Mention your Telegram ID: `{user_id}`\n"
            f"3️⃣ Admin will add searches within 5 minutes\n\n"
            f"💬 Owner: {OWNER_USERNAME}\n"
            f"📢 Channel: {CHANNEL_ID}",
            parse_mode="Markdown"
        )

# === MAIN ===
def main():
    Thread(target=run_flask).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("num", num_command))
    app.add_handler(CommandHandler("mylimit", mylimit))
    app.add_handler(CommandHandler("buy", buy_searches))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("logout", admin_logout))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("daily", admin_daily))
    app.add_handler(CommandHandler("monthly", admin_monthly))
    app.add_handler(CommandHandler("lifetime", admin_lifetime))
    app.add_handler(CommandHandler("payments", admin_payments))
    app.add_handler(CommandHandler("userinfo", admin_userinfo))
    app.add_handler(CommandHandler("add", admin_add))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("admincmds", admin_commands))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot started with:")
    print(f"   - {FREE_SEARCHES} free searches per user")
    print(f"   - ₹{PRICE_PER_SEARCH}/search after free limit")
    print(f"   - Auto-delete in {AUTO_DELETE_SECONDS} seconds")
    print(f"   - /num command available")
    print(f"   - /help command available")
    print(f"   - Admin commands ready")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True, timeout=30)

if __name__ == "__main__":
    main()
