from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import asyncio
import time
import logging
import os
from datetime import datetime
from flask import Flask
from threading import Thread

# === FLASK APP FOR PORT BINDING (Render के लिए जरूरी) ===
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Number Info Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# === LOGGING ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === कॉन्फ़िगरेशन ===
BOT_TOKEN = "8752831635:AAHkSr79OvCK55Q2QzPmnPUQ5Bf5Pa0Pin4"

# === नंबर इन्फो API ===
# आपकी पुरानी API जो काम कर रही थी
API_URL = "https://darkietech.site/numapi.php?action=api&key=AKASH&number={}"

# === चैनल ===
CHANNEL_USERNAME = "@shairecord"
CHANNEL_LINK = "https://t.me/shairecord"
CHANNEL_NAME = "SHAIRECORD"

# === एडमिन ===
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"  # अपना Telegram ID डालो

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

# === नंबर इन्फो फ़ेच करना ===
def get_number_info(phone_number: str):
    try:
        url = API_URL.format(phone_number)
        logger.info(f"API Call: {url}")
        response = requests.get(url, timeout=15)
        logger.info(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"API Response: {data}")
            
            if data.get("status") == "success" and data.get("result"):
                return data["result"]
        return None
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None

# === रिजल्ट फॉर्मेट करना ===
def format_result(phone: str, data):
    record = data[0] if isinstance(data, list) and data else data
    
    msg = f"🔍 *नंबर सर्च रिजल्ट*\n\n"
    msg += f"📱 *नंबर:* `{phone}`\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"👤 *नाम:* `{record.get('name', 'N/A')}`\n"
    msg += f"📛 *पहला नाम:* `{record.get('fname', 'N/A')}`\n"
    msg += f"📱 *मोबाइल:* `{record.get('num', phone)}`\n"
    msg += f"🔄 *अल्टरनेट:* `{record.get('alt', 'N/A')}`\n"
    msg += f"📍 *पता:* `{record.get('address', 'N/A')}`\n"
    msg += f"📡 *सर्कल:* `{record.get('circle', 'N/A')}`\n"
    
    # आधार नंबर
    aadhar = record.get('aadhar')
    if aadhar and str(aadhar).strip() and aadhar != "null":
        msg += f"🆔 *आधार:* `{aadhar}`\n"
    else:
        msg += f"🆔 *आधार:* `नहीं मिला`\n"
    
    msg += f"✉️ *ईमेल:* `{record.get('email', 'N/A')}`\n"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"⚡ *30 सेकंड में डिलीट होगा*\n"
    msg += f"🎉 *बिल्कुल मुफ्त!*"
    
    return msg

# === यूजर सर्च लॉग ===
def log_search(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_stats:
        user_stats[user_id] = {"total": 0, "daily": {}}
    user_stats[user_id]["total"] += 1
    if today not in user_stats[user_id]["daily"]:
        user_stats[user_id]["daily"][today] = 0
    user_stats[user_id]["daily"][today] += 1

# === ऑटो डिलीट ===
async def auto_delete(context, chat_id, msg_id, delay=30):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass

# === यूजर कमांड्स ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id in verified_users:
        stats = user_stats.get(user_id, {"total": 0})
        await update.message.reply_text(
            f"✅ *वापस स्वागत है!* {user.first_name}\n\n"
            f"🔍 कोई भी 10 अंकों का नंबर भेजें\n"
            f"📊 आपके कुल सर्च: `{stats['total']}`\n\n"
            f"📌 `/help` - मदद\n"
            f"👑 `/admin` - एडमिन लॉगिन",
            parse_mode="Markdown"
        )
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 जॉइन करें {CHANNEL_NAME}", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ मैं जॉइन कर चुका हूँ", callback_data="verify")]
    ])
    
    await update.message.reply_text(
        f"⚠️ *चैनल जॉइन करना जरूरी है* ⚠️\n\n"
        f"नमस्ते {user.first_name}!\n\n"
        f"बॉट उपयोग करने के लिए जॉइन करें:\n"
        f"📢 *{CHANNEL_NAME}*: {CHANNEL_LINK}\n\n"
        f"👇 *जॉइन करने के बाद बटन दबाएं*\n\n"
        f"🎉 *बिल्कुल मुफ्त!*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 *नंबर इन्फो बॉट - हेल्प गाइड*\n\n"
        f"1️⃣ चैनल जॉइन करें: {CHANNEL_LINK}\n"
        f"2️⃣ वेरिफाई करें\n"
        f"3️⃣ 10 अंकों का नंबर भेजें\n\n"
        f"🔹 `/num 9876543210` - नंबर सर्च\n"
        f"🔹 `/mystats` - अपने आंकड़े\n"
        f"🔹 `/ping` - बॉट स्टेटस\n\n"
        f"👑 एडमिन: @dinamic80\n"
        f"🎉 *बॉट पूरी तरह मुफ्त है!*",
        parse_mode="Markdown"
    )

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = user_stats.get(user_id, {"total": 0})
    await update.message.reply_text(
        f"📊 *आपके आंकड़े*\n\n"
        f"✅ कुल सर्च: `{stats['total']}`",
        parse_mode="Markdown"
    )

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
        f"🔍 कुल सर्च: `{sum(s['total'] for s in user_stats.values())}`\n"
        f"🎉 *बॉट 24x7 चालू है!*",
        parse_mode="Markdown"
    )

async def num_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if user_id not in verified_users:
        await update.message.reply_text("⚠️ पहले /start करके चैनल जॉइन करें और वेरिफाई करें!")
        return
    
    if not args:
        await update.message.reply_text("❌ उपयोग: `/num 9876543210`", parse_mode="Markdown")
        return
    
    phone = ''.join(filter(str.isdigit, args[0]))
    if len(phone) != 10:
        await update.message.reply_text("❌ कृपया 10 अंकों का सही नंबर भेजें")
        return
    
    msg = await update.message.reply_text(f"🔍 *खोज जारी...* `{phone}`", parse_mode="Markdown")
    await asyncio.sleep(1)
    
    result = get_number_info(phone)
    if result:
        log_search(user_id)
        result_msg = await update.message.reply_text(format_result(phone, result), parse_mode="Markdown")
        asyncio.create_task(auto_delete(context, result_msg.chat_id, result_msg.message_id, 30))
        asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id, 30))
        asyncio.create_task(auto_delete(context, update.message.chat_id, update.message.message_id, 30))
    else:
        err_msg = await update.message.reply_text(f"⚠️ नंबर `{phone}` की जानकारी नहीं मिली।\n\n• नंबर सही है?\n• नेटवर्क ठीक है?")
        asyncio.create_task(auto_delete(context, err_msg.chat_id, err_msg.message_id, 30))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in verified_users:
        await update.message.reply_text("⚠️ पहले /start करके चैनल जॉइन करें और वेरिफाई करें!")
        return
    
    phone = ''.join(filter(str.isdigit, update.message.text))
    if len(phone) == 10:
        msg = await update.message.reply_text(f"🔍 *खोज जारी...* `{phone}`", parse_mode="Markdown")
        await asyncio.sleep(1)
        
        result = get_number_info(phone)
        if result:
            log_search(user_id)
            result_msg = await update.message.reply_text(format_result(phone, result), parse_mode="Markdown")
            asyncio.create_task(auto_delete(context, result_msg.chat_id, result_msg.message_id, 30))
            asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id, 30))
            asyncio.create_task(auto_delete(context, update.message.chat_id, update.message.message_id, 30))
        else:
            err_msg = await update.message.reply_text(f"⚠️ नंबर `{phone}` की जानकारी नहीं मिली")
            asyncio.create_task(auto_delete(context, err_msg.chat_id, err_msg.message_id, 30))
    else:
        await update.message.reply_text("❌ कृपया 10 अंकों का सही नंबर भेजें")

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
            f"✅ *वेरिफिकेशन सफल!*\n\n"
            f"अब आप नंबर इन्फो बॉट का उपयोग कर सकते हैं।\n\n"
            f"🔍 कोई भी 10 अंकों का नंबर भेजें\n"
            f"🎉 *बिल्कुल मुफ्त!*\n\n"
            f"📌 `/help` - मदद के लिए",
            parse_mode="Markdown"
        )
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📢 जॉइन करें {CHANNEL_NAME}", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ मैं जॉइन कर चुका हूँ", callback_data="verify")]
        ])
        await query.message.edit_text(
            f"❌ *आप चैनल में शामिल नहीं हुए!*\n\n"
            f"कृपया पहले चैनल जॉइन करें:\n📢 {CHANNEL_LINK}\n\n"
            f"जॉइन करने के बाद फिर से वेरिफाई करें।",
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
        f"✅ *एडमिन एक्सेस दिया गया!*\n\n"
        f"👑 स्वागत है {update.effective_user.first_name}\n\n"
        f"📊 *बॉट स्टेटस*\n"
        f"• वेरिफाइड यूजर्स: `{len(verified_users)}`\n"
        f"• कुल सर्च: `{sum(s['total'] for s in user_stats.values())}`\n"
        f"🎉 *बॉट 24x7 चालू है!*\n\n"
        f"📋 *एडमिन कमांड:*\n"
        f"`/stats` - बॉट आंकड़े\n"
        f"`/users` - यूजर्स लिस्ट\n"
        f"`/userfind <id>` - यूजर ढूंढें\n"
        f"`/broadcast <msg>` - सभी को मैसेज\n"
        f"`/adminlogout` - लॉगआउट",
        parse_mode="Markdown"
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_searches = sum(s['total'] for s in user_stats.values())
    today = datetime.now().strftime("%Y-%m-%d")
    today_searches = sum(1 for s in user_stats.values() if s['daily'].get(today, 0))
    uptime_hours = (datetime.now() - bot_start_time).seconds // 3600
    
    await update.message.reply_text(
        f"📊 *बॉट आंकड़े*\n\n"
        f"👥 वेरिफाइड यूजर्स: `{len(verified_users)}`\n"
        f"🔍 कुल सर्च: `{total_searches}`\n"
        f"📅 आज के सर्च: `{today_searches}`\n"
        f"⏱️ अपटाइम: `{uptime_hours} घंटे`\n"
        f"📢 चैनल: {CHANNEL_NAME}\n"
        f"🎉 *बॉट मुफ्त और 24x7 चालू है!*",
        parse_mode="Markdown"
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verified_users:
        await update.message.reply_text("अभी कोई यूजर नहीं है")
        return
    
    msg = "📋 *यूजर्स लिस्ट*\n\n"
    for i, (uid, date) in enumerate(list(verified_users.items())[:20], 1):
        searches = user_stats.get(uid, {}).get('total', 0)
        msg += f"{i}. `{uid}` - {searches} सर्च\n"
    
    if len(verified_users) > 20:
        msg += f"\n... और {len(verified_users)-20} यूजर"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_userfind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ उपयोग: `/userfind <user_id>`\n\nउदाहरण: `/userfind 8481566006`", parse_mode="Markdown")
        return
    
    try:
        target = int(args[0])
        if target not in verified_users:
            await update.message.reply_text(f"❌ यूजर `{target}` नहीं मिला", parse_mode="Markdown")
            return
        
        stats = user_stats.get(target, {"total": 0})
        joined = verified_users[target].strftime("%Y-%m-%d %H:%M")
        
        await update.message.reply_text(
            f"👤 *यूजर इन्फो*\n\n"
            f"🆔 आईडी: `{target}`\n"
            f"✅ सर्च: `{stats['total']}`\n"
            f"📅 जॉइन: `{joined}`",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ सही यूजर आईडी भेजें")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ उपयोग: `/broadcast <संदेश>`\n\nउदाहरण: `/broadcast नया अपडेट आ गया है!`", parse_mode="Markdown")
        return
    
    msg = " ".join(args)
    success = 0
    fail = 0
    
    status = await update.message.reply_text("📢 ब्रॉडकास्ट शुरू...")
    
    for user_id in verified_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *घोषणा*\n\n{msg}\n\n─\n👑 @dinamic80",
                parse_mode="Markdown"
            )
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    
    await status.edit_text(f"✅ ब्रॉडकास्ट खत्म!\n\nसफल: `{success}`\nअसफल: `{fail}`", parse_mode="Markdown")

async def admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in admin_session:
        del admin_session[user_id]
    await update.message.reply_text("🔒 एडमिन सेशन खत्म हुआ")

# === एरर हैंडलर ===
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if "Conflict" in str(context.error):
        logger.warning("Conflict error – सिर्फ एक instance चलाएं")

# === MAIN ===
def main():
    # Flask thread शुरू करो (Render के लिए port bind करने के लिए)
    Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # यूजर कमांड्स
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mystats", mystats))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("num", num_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # एडमिन कमांड्स
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("userfind", admin_userfind))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("adminlogout", admin_logout))
    
    # कॉलबैक
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    
    # एरर हैंडलर
    app.add_error_handler(error_handler)
    
    print("="*50)
    print("✅ नंबर इन्फो बॉट चालू हो गया!")
    print(f"📢 चैनल: {CHANNEL_NAME}")
    print(f"👑 एडमिन: {ADMIN_CHAT_ID}")
    print(f"🔑 पासवर्ड: {ADMIN_PASSWORD}")
    print(f"🎉 बॉट 24x7 चालू रहेगा!")
    print("="*50)
    
    # drop_pending_updates=True से Conflict error ठीक होगा
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
