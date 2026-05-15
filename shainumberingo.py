import requests
import json
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# === Flask app for health check ===
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8080)

# === CONFIGURATION ===
BOT_TOKEN = "8988718117:AAHewU_hbW-Z6b49GFrTDlu-geKSsjriuEE"
API_URL = "https://darkietech.site/numapi.php?action=api&key=AKASH&number={}"
CHANNEL_ID = "https://t.me/norecorddis"
OWNER_USERNAME = "@dinamic80"
OWNER_NAME = "NO RECORD"
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"

admin_authenticated = {}

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

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID)],
        [InlineKeyboardButton("👑 Contact Owner", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
        [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")]
    ]
    await update.message.reply_text(
        f"📞 *Number Info Bot*\n👋 Hello {user.first_name}!\nSend a phone number.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_login(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Usage: `/admin <password>`", parse_mode="Markdown")
        return
    if args[0] == ADMIN_PASSWORD:
        admin_authenticated[user_id] = True
        await update.message.reply_text("✅ Admin access granted.")
    else:
        await update.message.reply_text("❌ Incorrect password.")

async def admin_logout(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id in admin_authenticated:
        del admin_authenticated[user_id]
        await update.message.reply_text("🔒 Admin session ended.")

@admin_required
async def stats(update: Update, context: CallbackContext):
    await update.message.reply_text("📊 Stats: Bot active.")

@admin_required
async def broadcast(update: Update, context: CallbackContext):
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("❌ Usage: `/broadcast <msg>`")
        return
    await update.message.reply_text(f"📢 Broadcast sent (simulated): {message}")

@admin_required
async def view_logs(update: Update, context: CallbackContext):
    await update.message.reply_text("📜 Logs: No errors reported.")

async def handle_number(update: Update, context: CallbackContext):
    user_input = update.message.text.strip()
    phone_number = ''.join(filter(str.isdigit, user_input))
    if len(phone_number) < 10:
        await update.message.reply_text("❌ Send a valid 10+ digit number.")
        return
    await update.message.chat.send_action(action="typing")
    info = get_number_info(phone_number)
    if not info or (isinstance(info, dict) and "error" in info):
        await update.message.reply_text("⚠️ No information found.")
        return
    record = info[0] if isinstance(info, list) and info else info
    message = f"🔍 *Results for {phone_number}*\n👤 Name: {record.get('name', 'N/A')}\n📱 Number: {record.get('num', phone_number)}\n🆔 Aadhar: {record.get('aadhar', 'N/A')}\n📍 Address: {record.get('address', 'N/A')}"
    keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID)]]
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == "new":
        await query.message.reply_text("Send another number:")
    elif query.data == "about":
        await query.message.reply_text(f"Owner: {OWNER_NAME} {OWNER_USERNAME}\nChannel: {CHANNEL_ID}")

async def unknown(update: Update, context: CallbackContext):
    await update.message.reply_text("Send a phone number or /admin to login.")

# === MAIN ===
def main():
    # Start Flask thread
    Thread(target=run_flask).start()
    
    # Start bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_login))
    app.add_handler(CommandHandler("logout", admin_logout))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("logs", view_logs))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot starting with Flask health check...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
