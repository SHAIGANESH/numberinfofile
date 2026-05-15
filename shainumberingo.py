from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import asyncio
import time
import logging
from datetime import datetime
import os

# === LOGGING ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === कॉन्फ़िगरेशन ===
BOT_TOKEN = "8752831635:AAHkSr79OvCK55Q2QzPmnPUQ5Bf5Pa0Pin4"

# RC API – ध्यान दें: यह API 401 error दे रही है, सही key चाहिए
API_URL = "https://rc-info-api.onrender.com/apis/vehicle_rc_info?key={}&rc={}"
API_KEY = "demo"  # ⚠️ बदलना है – सही key डालो

# === चैनल ===
CHANNEL_USERNAME = "@shairecord"
CHANNEL_LINK = "https://t.me/shairecord"
CHANNEL_NAME = "SHAIRECORD"

# === एडमिन ===
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"

# === डाटा स्टोर ===
verified_users = {}
user_stats = {}
admin_session = {}
bot_start_time = datetime.now()

# === चैनल मेंबरशिप चेक ===
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Member check error: {e}")
        return False

# === RC व्हीकल इन्फो ===
def get_vehicle_info(rc_number: str):
    try:
        rc_clean = rc_number.upper().replace(" ", "")
        url = API_URL.format(API_KEY, rc_clean)
        logger.info(f"API Call: {url}")
        
        response = requests.get(url, timeout=15)
        logger.info(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"API Response: {data}")
            return data
        return None
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None

# === रिजल्ट फॉर्मेट ===
def format_result(rc: str, data: dict):
    msg = f"🚗 *वाहन RC सूचना*\n\n"
    msg += f"🔢 *RC:* `{rc.upper()}`\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if isinstance(data, dict):
        for key, value in data.items():
            if value and str(value).strip() and value != "null" and key not in ["status", "success"]:
                msg += f"• {key}: `{value}`\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━\n⚡ 30 सेकंड में डिलीट\n🎉 *मुफ्त!*"
    return msg

def log_search(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_stats:
        user_stats[user_id] = {"total": 0, "daily": {}}
    user_stats[user_id]["total"] += 1
    user_stats[user_id]["daily"][today] = user_stats[user_id]["daily"].get(today, 0) + 1

async def auto_delete(context, chat_id, msg_id, delay=30):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except:
        pass

# === यूजर कमांड्स ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id in verified_users:
        stats = user_stats.get(user_id, {"total": 0})
        await update.message.reply_text(
            f"✅ *वापस स्वागत!* {user.first_name}\n\n"
            f"🔍 RC नंबर भेजें (जैसे: `MH12DE1433`)\n"
            f"📊 कुल सर्च: `{stats['total']}`\n\n"
            f"📌 `/help` - मदद\n👑 `/admin` - एडमिन",
            parse_mode="Markdown"
        )
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 जॉइन करें {CHANNEL_NAME}", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ जॉइन कर चुका", callback_data="verify")]
    ])
    
    await update.message.reply_text(
        f"⚠️ *चैनल जॉइन जरूरी*\n\n"
        f"नमस्ते {user.first_name}!\n"
        f"👇 जॉइन करें: {CHANNEL_LINK}\n"
        f"👇 फिर '✅ जॉइन कर चुका' दबाएं\n\n🎉 *मुफ्त!*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 *हेल्प*\n\n"
        f"1️⃣ चैनल जॉइन करें: {CHANNEL_LINK}\n"
        f"2️⃣ वेरिफाई करें\n"
        f"3️⃣ RC नंबर भेजें\n\n"
        f"🔹 `/rc MH12DE1433` - RC सर्च\n"
        f"🔹 `/mystats` - आंकड़े\n"
        f"🔹 `/ping` - स्टेटस\n\n"
        f"👑 एडमिन: @dinamic80",
        parse_mode="Markdown"
    )

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = user_stats.get(user_id, {"total": 0})
    await update.message.reply_text(f"📊 *आपके सर्च:* `{stats['total']}`", parse_mode="Markdown")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    await update.message.reply_text("🏓 पिंग...")
    end = time.time()
    uptime_sec = (datetime.now() - bot_start_time).seconds
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    
    await update.message.reply_text(
        f"🏓 *पोंग!*\n\n"
        f"📡 लेटेंसी: `{round((end-start)*1000)}ms`\n"
        f"⏱️ अपटाइम: `{hours}h {minutes}m`\n"
        f"👥 यूजर्स: `{len(verified_users)}`\n"
        f"🔍 सर्च: `{sum(s['total'] for s in user_stats.values())}`",
        parse_mode="Markdown"
    )

async def rc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if user_id not in verified_users:
        await update.message.reply_text("⚠️ पहले /start करें और चैनल जॉइन करें!")
        return
    
    if not args:
        await update.message.reply_text("❌ उपयोग: `/rc MH12DE1433`", parse_mode="Markdown")
        return
    
    rc_number = args[0].upper().replace(" ", "")
    msg = await update.message.reply_text(f"🔍 *ढूंढ रहा हूँ...* `{rc_number}`", parse_mode="Markdown")
    
    result = get_vehicle_info(rc_number)
    if result:
        log_search(user_id)
        result_msg = await update.message.reply_text(format_result(rc_number, result), parse_mode="Markdown")
        asyncio.create_task(auto_delete(context, result_msg.chat_id, result_msg.message_id, 30))
        asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id, 30))
        asyncio.create_task(auto_delete(context, update.message.chat_id, update.message.message_id, 30))
    else:
        err_msg = await update.message.reply_text(f"⚠️ RC `{rc_number}` की जानकारी नहीं मिली।\n• API key सही है? (demo काम नहीं करेगी)\n• RC नंबर सही है?")
        asyncio.create_task(auto_delete(context, err_msg.chat_id, err_msg.message_id, 30))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in verified_users:
        await update.message.reply_text("⚠️ पहले /start करें और चैनल जॉइन करें!")
        return
    
    text = update.message.text.strip().upper().replace(" ", "")
    if len(text) >= 6 and len(text) <= 12:
        msg = await update.message.reply_text(f"🔍 *ढूंढ रहा हूँ...* `{text}`", parse_mode="Markdown")
        result = get_vehicle_info(text)
        if result:
            log_search(user_id)
            result_msg = await update.message.reply_text(format_result(text, result), parse_mode="Markdown")
            asyncio.create_task(auto_delete(context, result_msg.chat_id, result_msg.message_id, 30))
            asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id, 30))
            asyncio.create_task(auto_delete(context, update.message.chat_id, update.message.message_id, 30))
        else:
            err_msg = await update.message.reply_text(f"⚠️ RC `{text}` नहीं मिला")
            asyncio.create_task(auto_delete(context, err_msg.chat_id, err_msg.message_id, 30))

# === वेरिफिकेशन ===
async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if await is_member(user_id, context):
        verified_users[user_id] = datetime.now()
        if user_id not in user_stats:
            user_stats[user_id] = {"total": 0, "daily": {}}
        await query.message.edit_text(
            f"✅ *वेरिफाइड!*\n\nअब RC नंबर भेजें।\n🎉 *मुफ्त!*",
            parse_mode="Markdown"
        )
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📢 जॉइन करें {CHANNEL_NAME}", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ जॉइन कर चुका", callback_data="verify")]
        ])
        await query.message.edit_text(
            f"❌ *आप चैनल में नहीं हैं!*\nपहले जॉइन करें: {CHANNEL_LINK}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

# === एडमिन कमांड्स ===
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ आप एडमिन नहीं हैं!")
        return
    
    if not args or args[0] != ADMIN_PASSWORD:
        await update.message.reply_text(f"❌ गलत पासवर्ड!\nउपयोग: `/admin {ADMIN_PASSWORD}`", parse_mode="Markdown")
        return
    
    admin_session[user_id] = True
    await update.message.reply_text(
        f"✅ *एडमिन एक्सेस*\n\n"
        f"👑 वेरिफाइड: `{len(verified_users)}`\n"
        f"🔍 कुल सर्च: `{sum(s['total'] for s in user_stats.values())}`\n\n"
        f"📋 कमांड:\n`/stats` `/users` `/userfind <id>` `/broadcast <msg>`",
        parse_mode="Markdown"
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = sum(s['total'] for s in user_stats.values())
    await update.message.reply_text(
        f"📊 *आंकड़े*\n👥 यूजर्स: `{len(verified_users)}`\n🔍 सर्च: `{total}`",
        parse_mode="Markdown"
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verified_users:
        await update.message.reply_text("कोई यूजर नहीं")
        return
    msg = "📋 *यूजर्स*\n"
    for i, uid in enumerate(list(verified_users.keys())[:20], 1):
        s = user_stats.get(uid, {}).get('total', 0)
        msg += f"{i}. `{uid}` - {s} सर्च\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_userfind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ `/userfind <id>`")
        return
    try:
        uid = int(args[0])
        if uid not in verified_users:
            await update.message.reply_text("यूजर नहीं मिला")
            return
        s = user_stats.get(uid, {}).get('total', 0)
        await update.message.reply_text(f"👤 यूजर `{uid}`\n✅ सर्च: `{s}`", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ गलत ID")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ `/broadcast <संदेश>`")
        return
    msg = " ".join(args)
    success = 0
    status = await update.message.reply_text("📢 ब्रॉडकास्ट...")
    for uid in verified_users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 *घोषणा*\n\n{msg}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await status.edit_text(f"✅ भेजा: `{success}` यूजर्स को")

async def admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in admin_session:
        del admin_session[uid]
    await update.message.reply_text("🔒 लॉगआउट")

# === एरर हैंडलर ===
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if "Conflict" in str(context.error):
        logger.warning("Conflict error – कृपया सुनिश्चित करें कि bot की केवल एक instance चल रही है")

# === मेन ===
def main():
    # Render पर PORT वेरिएबल सेट है तो उसे इस्तेमाल करें, वरना डिफॉल्ट 8080
    port = int(os.environ.get("PORT", 8080))
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # हैंडलर
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mystats", mystats))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("rc", rc_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("userfind", admin_userfind))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("adminlogout", admin_logout))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    app.add_error_handler(error_handler)
    
    print("="*50)
    print("✅ RC बॉट चालू!")
    print(f"📢 चैनल: {CHANNEL_NAME}")
    print("🎉 मुफ्त और 24x7")
    print("="*50)
    
    # ⚡ CONFLICT FIX: drop_pending_updates=True से पुराने updates हट जाएंगे
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
