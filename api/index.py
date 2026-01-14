import os
import json
import asyncio
from io import BytesIO
from http.server import BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from deep_translator import GoogleTranslator
from rembg import remove

# 1. Setup
TOKEN = os.getenv("BOT_TOKEN")
application = ApplicationBuilder().token(TOKEN).build()

# 2. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🌍 Translate", callback_data='trans')],
                [InlineKeyboardButton("🖼️ Remove BG", callback_data='bg')]]
    await update.message.reply_text("Welcome! Choose a tool:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['action'] = query.data
    await query.edit_message_text(f"Send your {'text' if query.data == 'trans' else 'photo'} now.")

async def process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action')
    if action == 'trans' and update.message.text:
        res = GoogleTranslator(source='auto', target='en').translate(update.message.text)
        await update.message.reply_text(f"📝 {res}")
    elif action == 'bg' and update.message.photo:
        await update.message.reply_text("⏳ AI is working (this may take 15s)...")
        file = await context.bot.get_file(update.message.photo[-1].file_id)
        img = await file.download_as_bytearray()
        await update.message.reply_photo(photo=BytesIO(remove(img)), caption="✅ Done!")

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(handle_choice))
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, process))

# 3. Stable Vercel Class Handler
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.process_telegram(post_data))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    async def process_telegram(self, data):
        if not application.running:
            await application.initialize()
        update = Update.de_json(json.loads(data), application.bot)
        await application.process_update(update)

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<h1>Bot Status: Online ✅</h1>")
