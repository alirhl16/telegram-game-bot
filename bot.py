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

# =========================
# تنظیمات ربات
# =========================
TOKEN = os.environ.get("TOKEN")  # توکن ربات از ENV
BOT_USERNAME = os.environ.get("BOT_USERNAME")  # یوزرنیم ربات از ENV

bot = Bot(token=TOKEN)
app_flask = Flask(__name__)

# =========================
# داده‌های بازی
# =========================
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
    chat_id = query.from_user.id

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
    elif query.data.startswith("start_"):
        code = query.data.split("_")[1]
        game = bot_data_store[code]
        if not game["started"]:
            game["started"] = True
            for p, cid in game["players"].items():
                await bot.send_message(chat_id=cid, text="▶️ بازی شروع شد!")
            await start_round(code)
    elif query.data.startswith("vote_"):
        data = query.data.split("_")
        code = data[1]
        message_id = int(data[2])
        game = bot_data_store[code]
        winner = game["message_map"][message_id]
        game["scores"][winner] += 1
        for p, cid in game["players"].items():
            await bot.send_message(chat_id=cid, text=f"🏆 برنده راند: {winner}")
        game["judge_index"] += 1
        await start_round(code)

# =========================
# شروع راند
# =========================
async def start_round(code):
    game = bot_data_store[code]
    game["round"] += 1
    if game["round"] > 20:
        scores_text = "📊 جدول امتیازات نهایی:\n"
        for p, score in game["scores"].items():
            scores_text += f"{p}: {score}\n"
        winner = max(game["scores"], key=game["scores"].get)
        scores_text += f"🎉 برنده نهایی: {winner}"
        for p, cid in game["players"].items():
            await bot.send_message(chat_id=cid, text=scores_text)
        del bot_data_store[code]
        return

    players = list(game["players"].keys())
    judge = players[game["judge_index"] % len(players)]
    game["responses"] = {}
    game["message_map"] = {}
    scenario = random.choice(scenarios)
    for p, cid in game["players"].items():
        if p == judge:
            await bot.send_message(
                chat_id=cid,
                text=f"(Pov:)\n{scenario}\n(شما داور هستید، برای انتخاب برنده روی گزینه زیر ضربه بزنید)"
            )
        else:
            await bot.send_message(
                chat_id=cid,
                text=f"(Pov:)\n{scenario}\nاستیکر یا گیف خود را ارسال کنید"
            )

# =========================
# پیوستن با کد بازی
# =========================
async def handle_code_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    if text.isdigit() and text in bot_data_store:
        game = bot_data_store[text]
        if user not in game["players"]:
            game["players"][user] = chat_id
            game["scores"][user] = 0
            await update.message.reply_text(f"✅ {user} با موفقیت به بازی {text} اضافه شد!")
            creator_name = list(game["players"].keys())[0]
            creator_chat_id = game["players"][creator_name]
            if creator_chat_id != chat_id:
                await bot.send_message(chat_id=creator_chat_id, text=f"✅ {user} به بازی اضافه شد!")
        else:
            await update.message.reply_text(f"❌ {user} قبلاً به بازی اضافه شده است!")
    else:
        await update.message.reply_text("❌ کد بازی معتبر نیست یا بازی پیدا نشد.")

# =========================
# دریافت GIF / استیکر
# =========================
async def handle_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name
    message = update.message
    for code, game in bot_data_store.items():
        judge = list(game["players"].keys())[game["judge_index"] % len(game["players"])]
        if user in game["players"] and user != judge:
            if message.sticker or message.animation:
                game["responses"][user] = message
                game["message_map"][message.message_id] = user
                for p, cid in game["players"].items():
                    if message.sticker:
                        await bot.send_sticker(chat_id=cid, sticker=message.sticker.file_id)
                    elif message.animation:
                        await bot.send_animation(chat_id=cid, animation=message.animation.file_id)
                keyboard = [[InlineKeyboardButton("🏆 انتخاب برنده", callback_data=f"vote_{code}_{message.message_id}")]]
                await bot.send_message(
                    chat_id=game["players"][judge],
                    text="استیکر یا گیف برای رأی گیری:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

# =========================
# شروع بازی عمومی خودکار
# =========================
async def try_start_public_game():
    global matchmaking_queue
    while 2 <= len(matchmaking_queue) <= 5:
        players = matchmaking_queue[:5]
        matchmaking_queue = matchmaking_queue[5:]
        code = generate_game_code()
        game = {"players": {u: cid for u, cid in players}, "scores": {u: 0 for u,_ in players}, "started": True,
                "judge_index":0, "round":0, "responses":{}, "message_map":{}}
        bot_data_store[code] = game
        for u, cid in players:
            await bot.send_message(chat_id=cid, text=f"▶️ بازی عمومی شروع شد! کد بازی: {code}")
        await start_round(code)

# =========================
# راه‌اندازی ربات
# =========================
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_code_message))
application.add_handler(MessageHandler(filters.STICKER.ALL | filters.ANIMATION, handle_meme))

# =========================
# Flask برای Webhook
# =========================
@app_flask.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put(update)
    return "ok"

@app_flask.route("/")
def index():
    return "Bot is running"

# =========================
# اجرای Web Service روی Render
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)