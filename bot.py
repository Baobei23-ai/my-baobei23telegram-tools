
import os
import logging
import sqlite3
import pandas as pd
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler, ChatMemberHandler, ConversationHandler

# --- 0. CONFIGURATION ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
TARGET_GROUP_ID = int(os.getenv("GROUP_ID"))
GROUP_LINK = "https://t.me/+fbFo_1M1wZA5ZThl"
ADMIN_CONTACT_LINK = "https://t.me/Azwz1233"
BROADCASTING = 1

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 1. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('nexus_vault.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS members 
                      (user_id INTEGER PRIMARY KEY, name TEXT, status TEXT DEFAULT 'pending', 
                       created_at TEXT, last_reminder_at TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, amount REAL, date TEXT)''')
    conn.commit()
    conn.close()

async def update_member_status(user_id, status, name=None):
    conn = sqlite3.connect('nexus_vault.db')
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if name:
        conn.cursor().execute("INSERT OR REPLACE INTO members (user_id, name, status, created_at, last_reminder_at) VALUES (?, ?, ?, ?, ?)", 
                             (user_id, name, status, now, now))
    else:
        conn.cursor().execute("UPDATE members SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

# --- 2. THE CONTINUOUS 3-MINUTE MONITOR ---
async def global_live_monitor(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('nexus_vault.db')
    try:
        users = conn.cursor().execute("SELECT user_id, name, last_reminder_at FROM members WHERE status = 'pending'").fetchall()
        for uid, name, last_remind in users:
            if uid == ADMIN_ID: continue
            last_time = datetime.strptime(last_remind, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= last_time + timedelta(minutes=3):
                msg = f"🚨 **Time's Up {name}!**\nဘေလ် SS ပို့ရန် ၃ မိနစ်ကျော်သွားပါပြီ။"
                try: await context.bot.send_message(chat_id=uid, text=msg)
                except: pass
                try: await context.bot.send_message(chat_id=TARGET_GROUP_ID, text=f"⚠️ [ID: `{uid}`] {msg}")
                except: pass
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                conn.cursor().execute("UPDATE members SET last_reminder_at = ? WHERE user_id = ?", (now_str, uid))
                conn.commit()
    finally: conn.close()

# --- 3. KEYBOARDS ---
def get_admin_keyboard():
    return ReplyKeyboardMarkup([['📊 Today Report', '📥 Export Excel'], ['📢 Broadcast', '⚙️ Check Pending']], resize_keyboard=True)

def get_user_keyboard():
    return ReplyKeyboardMarkup([['💳 Payment Info', '🚀 Start Bot'], ['📞 Contact Admin']], resize_keyboard=True)

# --- 4. ADMIN & BROADCAST LOGIC ---
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("📢 **Broadcast Mode**\nစာသား သို့မဟုတ် ပုံ ပို့ပေးပါ။ ရပ်ရန် /cancel")
    return BROADCASTING

async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('nexus_vault.db')
    users = conn.cursor().execute("SELECT user_id FROM members").fetchall()
    conn.close()
    for (uid,) in users:
        try:
            if update.message.photo: await context.bot.send_photo(chat_id=uid, photo=update.message.photo[-1].file_id, caption=update.message.caption)
            else: await context.bot.send_message(chat_id=uid, text=update.message.text)
            await asyncio.sleep(0.05)
        except: continue
    await update.message.reply_text("✅ Done.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# --- 5. TEXT HANDLERS ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, uid = update.message.text, update.effective_user.id
    if text == '🚀 Start Bot' or text == '/start':
        await update_member_status(uid, 'pending', update.effective_user.full_name)
        kb = get_admin_keyboard() if uid == ADMIN_ID else get_user_keyboard()
        await update.message.reply_text("🚀 Nexus Velocity Active!", reply_markup=kb)
    elif text == '📊 Today Report' and uid == ADMIN_ID:
        conn = sqlite3.connect('nexus_vault.db')
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        total = conn.cursor().execute("SELECT SUM(amount) FROM transactions WHERE date=?", (today,)).fetchone()[0] or 0.0
        conn.close()
        await update.message.reply_text(f"📊 **Income:** {total:,.0f} MMK")

# --- 6. MAIN ---
if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.job_queue.run_repeating(global_live_monitor, interval=30, first=10)
    bc_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📢 Broadcast$'), start_broadcast)],
        states={BROADCASTING: [MessageHandler(filters.PHOTO | filters.TEXT & (~filters.COMMAND), execute_broadcast)]},
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    app.add_handler(bc_handler)
    app.add_handler(CommandHandler('start', handle_text))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(CallbackQueryHandler(lambda u, c: None)) # Placeholder
    app.run_polling()
