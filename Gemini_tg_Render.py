import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from google import genai

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
MY_TELEGRAM_USER_ID = 1315965956

ai_client = genai.Client(api_key=GEMINI_API_KEY)
chat_sessions = {}

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "OK", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def get_or_create_chat(chat_id: int):
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = ai_client.aio.chats.create(model=GEMINI_MODEL_NAME)
    return chat_sessions[chat_id]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id != MY_TELEGRAM_USER_ID:
        await context.bot.send_message(
            chat_id=MY_TELEGRAM_USER_ID, 
            text=f"User {user.first_name} (@{user.username}) just started the bot."
        )
    await update.message.reply_text("Hello! I am ready. Just send me a message and I will reply.")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
    await update.message.reply_text("History cleared! Starting a fresh conversation.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    user = update.message.from_user
    chat_id = update.effective_chat.id

    if user.id != MY_TELEGRAM_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=MY_TELEGRAM_USER_ID,
                text=f"From {user.first_name} (@{user.username}):\n{user_text}"
            )
        except Exception as e:
            logging.error(f"Failed to forward message to admin: {e}")

    status_message = await update.message.reply_text("Generating...")

    try:
        chat = get_or_create_chat(chat_id)
        response = await chat.send_message(user_text)
        await status_message.edit_text(response.text)
    except Exception as e:
        logging.error(f"Error calling Gemini API: {e}")
        await status_message.edit_text("Sorry, I ran into an error generating that response.")

def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN is missing!")
        return

    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()