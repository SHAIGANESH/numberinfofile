from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import asyncio
import time
from datetime import datetime

# === CONFIGURATION ===
BOT_TOKEN = "8465239312:AAE2WJf_vBLe-iAFLEJCIlZ5B-MeaH434Yg"
API_URL = "https://movements-invoice-amanda-victoria.trycloudflare.com/search/number?number={}&key=mysecretkey123"

# === SINGLE CHANNEL ===
CHANNEL_USERNAME = "@shairecord"
CHANNEL_LINK = "https://t.me/shairecord"
CHANNEL_NAME = "SHAIRECORD"

# === ADMIN CONFIG ===
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"  # आपका Telegram ID

# === STORAGE ===
verified_users = {}
user_stats = {}
admin_session = {}
bot_start_time = datetime.now()

# === CHECK CHANNEL MEMBERSHIP ===
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# === LOG SEARCH ===
def log_search(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_stats:
        user_stats[user_id] = {"total": 0, "daily": {}}
    user_stats[user_id]["total"] += 1
    if today not in user_stats[user_id]["daily"]:
        user_stats[user_id]["daily"][today] = 0
    user_stats[user_id]["daily"][today] += 1

# === GET NUMBER INFO ===
def get_number_info(phone: str):
    try:
        url = API_URL.format(phone)
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("status") == "success" and data.get("result"):
            return data["result"][0]
        return None
    except:
        return None

# === USER COMMANDS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id in verified_users:
        await update.message.reply_text(
            f"✅ *वापस स्वागत है!* {user.first_name}\n\n"
            f"🔍 कोई भी 10 अंकों का नंबर भेजें\n"
            f"📊 आपके कुल सर्च: `{user_stats.get(user_id, {}).get('total', 0)}`\n\n"
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
        f"⚠️ *चैनल जॉइन करना जरूरी है*\n\n"
        f"नमस्ते {user.first_name}!\n\n"
        f"बॉट उपयोग करने के लिए जॉइन करें:\n"
        f"📢 {CHANNEL_NAME}: {CHANNEL_LINK}\n\n"
        f"👇 *जॉइन करने के बाद वेरिफाई बटन दबाएं*\n\n"
        f"🎉 *बिल्कुल मुफ्त!*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 *हेल्प गाइड*\n\n"
        f"1️⃣ चैनल जॉइन करें\n"
        f"2️⃣ वेरिफाई करें\n"
        f"3️⃣ 10 अंकों का नंबर भेजें\n\n"
        f"🔹 `/num 9876543210` - नंबर सर्च\n"
        f"🔹 `/mystats` - अपने आंकड़े\n"
        f"🔹 `/ping` - बॉट स्टेटस\n\n"
        f"👑 एडमिन: @dinamic80",
        parse_mode="Markdown"
    )

async def mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = user_stats.get(user_id, {"total": 0})
    await update.message.reply_text(
        f"📊 *आपके आंकड़े*\n\n"
        f"✅ कुल सर्च: `{stats['total']}`\n"
        f"📅 पहली बार: `{verified_users.get(user_id, datetime.now()).strftime('%Y-%m-%d') if user_id in verified_users else 'अभी नहीं'}`",
        parse_mode="Markdown"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    await update.message.reply_text("🏓 पिंग...")
    end = time.time()
    uptime = (datetime.now() - bot_start_time).seconds // 60
    await update.message.reply_text(
        f"🏓 *पोंग!*\n\n"
        f"📡 लेटेंसी: `{round((end-start)*1000)}ms`\n"
        f"⏱️ अपटाइम: `{uptime} मिनट`\n"
        f"👥 यूजर्स: `{len(verified_users)}`\n"
        f"🔍 सर्च: `{sum(s['total'] for s in user_stats.values())}`",
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
    
    await update.message.reply_text(f"🔍 *खोज जारी...* `{phone}`", parse_mode="Markdown")
    
    result = get_number_info(phone)
    if result:
        log_search(user_id)
        msg = f"📞 *नतीजा*\n\n"
        msg += f"👤 नाम: `{result.get('name', 'N/A')}`\n"
        msg += f"📍 पता: `{result.get('address', 'N/A')}`\n"
        msg += f"🆔 आधार: `{result.get('aadhar', 'N/A')}`\n"
        msg += f"📱 नंबर: `{result.get('num', phone)}`"
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ कोई जानकारी नहीं मिली")

async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in verified_users:
        await update.message.reply_text("⚠️ पहले /start करके चैनल जॉइन करें और वेरिफाई करें!")
        return
    
    phone = ''.join(filter(str.isdigit, update.message.text))
    if len(phone) == 10:
        await update.message.reply_text(f"🔍 *खोज जारी...* `{phone}`", parse_mode="Markdown")
        result = get_number_info(phone)
        if result:
            log_search(user_id)
            msg = f"📞 *नतीजा*\n\n👤 नाम: `{result.get('name', 'N/A')}`\n📍 पता: `{result.get('address', 'N/A')}`"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ कोई जानकारी नहीं मिली")
    else:
        await update.message.reply_text("❌ कृपया 10 अंकों का सही नंबर भेजें")

# === VERIFICATION CALLBACK ===
async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if await is_member(user_id, context):
        verified_users[user_id] = datetime.now()
        if user_id not in user_stats:
            user_stats[user_id] = {"total": 0, "daily": {}}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 मेरे आंकड़े", callback_data="mystats")],
            [InlineKeyboardButton("❓ मदद", callback_data="help")]
        ])
        
        await query.message.edit_text(
            f"✅ *वेरिफिकेशन सफल!*\n\n"
            f"अब आप बॉट का उपयोग कर सकते हैं।\n\n"
            f"🔍 कोई भी 10 अंकों का नंबर भेजें।\n"
            f"🎉 *बिल्कुल मुफ्त!*",
            parse_mode="Markdown",
            reply_markup=keyboard
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

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "verify":
        await verify_callback(update, context)
    elif query.data == "mystats":
        stats = user_stats.get(user_id, {"total": 0})
        await query.message.reply_text(f"📊 आपके कुल सर्च: `{stats['total']}`", parse_mode="Markdown")
    elif query.data == "help":
        await help_command(update, context)

# === ADMIN COMMANDS ===
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
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 बॉट स्टैट्स", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 यूजर्स लिस्ट", callback_data="admin_users")],
        [InlineKeyboardButton("👤 यूजर सर्च", callback_data="admin_userfind")],
        [InlineKeyboardButton("📢 ब्रॉडकास्ट", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔒 लॉगआउट", callback_data="admin_logout")]
    ])
    
    await update.message.reply_text(
        f"✅ *एडमिन एक्सेस दिया गया!*\n\n"
        f"👑 स्वागत है {update.effective_user.first_name}\n\n"
        f"📊 *बॉट स्टेटस*\n"
        f"• वेरिफाइड यूजर्स: `{len(verified_users)}`\n"
        f"• कुल सर्च: `{sum(s['total'] for s in user_stats.values())}`\n\n"
        f"नीचे दिए बटन का उपयोग करें:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_searches = sum(s['total'] for s in user_stats.values())
    today = datetime.now().strftime("%Y-%m-%d")
    today_searches = sum(1 for s in user_stats.values() if s['daily'].get(today, 0))
    
    await update.message.reply_text(
        f"📊 *बॉट आंकड़े*\n\n"
        f"👥 वेरिफाइड यूजर्स: `{len(verified_users)}`\n"
        f"🔍 कुल सर्च: `{total_searches}`\n"
        f"📅 आज के सर्च: `{today_searches}`\n"
        f"⏱️ अपटाइम: `{(datetime.now() - bot_start_time).seconds // 3600} घंटे`\n"
        f"🎉 *बॉट मुफ्त है!*",
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
    
    target = args[0]
    if int(target) not in verified_users:
        await update.message.reply_text(f"❌ यूजर `{target}` नहीं मिला", parse_mode="Markdown")
        return
    
    uid = int(target)
    stats = user_stats.get(uid, {"total": 0})
    joined = verified_users[uid].strftime("%Y-%m-%d %H:%M")
    
    await update.message.reply_text(
        f"👤 *यूजर इन्फो*\n\n"
        f"🆔 आईडी: `{uid}`\n"
        f"✅ सर्च: `{stats['total']}`\n"
        f"📅 जॉइन: `{joined}`\n"
        f"🎉 *बॉट मुफ्त है!*",
        parse_mode="Markdown"
    )

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

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()
    
    if user_id != ADMIN_CHAT_ID:
        await query.message.reply_text("❌ आप एडमिन नहीं हैं!")
        return
    
    if query.data == "admin_stats":
        await admin_stats(update, context)
    elif query.data == "admin_users":
        await admin_users(update, context)
    elif query.data == "admin_userfind":
        await query.message.reply_text("📌 `/userfind <user_id>` का उपयोग करें\nउदाहरण: `/userfind 8481566006`")
    elif query.data == "admin_broadcast":
        await query.message.reply_text("📌 `/broadcast <संदेश>` का उपयोग करें")
    elif query.data == "admin_logout":
        await admin_logout(update, context)

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("mystats", mystats))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("num", num_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("userfind", admin_userfind))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("adminlogout", admin_logout))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^(verify|mystats|help)$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    
    print("✅ बॉट चालू है! चैनल: @shairecord")
    print(f"📊 एडमिन कमांड: /admin {ADMIN_PASSWORD}")
    app.run_polling()

if __name__ == "__main__":
    main()
