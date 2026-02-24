import logging
import random
import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
bot = Bot(token=TOKEN)
app_flask = Flask(__name__)

scenarios = ["😂 وقتی شارژت تموم شد", "😹 وقتی با گوشی دستشویی میری!"]
matchmaking_queue = []
bot_data_store = {}

def generate_game_code():
    return str(random.randint(1000, 9999))

# =========================
# پنل کاربری
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 شروع بازی با بقیه", callback_data="public_game")],
        [InlineKeyboardButton("🛠 ساخت بازی اختصاصی", callback_data="private_game")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "سلام! به پنل کاربری خوش آمدید. یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=reply_markup
    )

# =========================
# دکمه‌ها
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.first_name
    chat_id = query.from_user.id  # اصلاح شد

    if query.data == "private_game":
        code = generate_game_code()
        bot_data_store[code] = {
            "players": {user: chat_id},
            "scores": {user: 0},
            "started": False,
            "judge_index": 0,
            "round": 0,
            "responses": {},
            "message_map": {}
        }
        keyboard = [[InlineKeyboardButton("▶️ شروع بازی", callback_data=f"start_{code}")]]
        await query.edit_message_text(
            f"🎉 بازی اختصاصی ساخته شد! شما سازنده هستید.\nکد بازی: {code}\nبازیکنان دیگر می‌توانند با این کد وارد شوند.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "public_game":
        if (user, chat_id) not in matchmaking_queue:
            matchmaking_queue.append((user, chat_id))
        await query.edit_message_text("⏳ شما وارد صف بازی عمومی شدید. منتظر بازیکنان دیگر باشید...")
        await try_start_public_game()
    # بقیه بخش‌های start_ و vote_ بدون تغییر

# =========================
# Flask Webhook
# =========================
@app_flask.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    # پردازش update توسط اپلیکیشن
    application = ApplicationBuilder().token(TOKEN).build()
    application.update_queue.put(update)
    return "ok"

@app_flask.route("/")
def index():
    return "Bot is running"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)