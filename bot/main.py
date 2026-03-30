import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT, validate
from database import save_student, get_daily_note, get_all_notes, get_questions, get_answer, get_books
from gemini import ask_gemini

# Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ COMMAND HANDLERS ============

async def start(update: Update, context):
    user = update.effective_user
    save_student(user)
    
    text = f"""🎓 *Welcome {user.first_name}!*

I'm EduBot - your AI learning assistant.

📅 /daily - Today's note
❓ /questions - Practice questions
🤖 /ask [question] - Chat with AI
📚 /books - View books
📋 /allnotes - All notes
🔢 /answer [number] - Get answer

Type a command to start learning! 🚀"""
    
    await update.message.reply_text(text, parse_mode='Markdown')
    logger.info(f"User {user.id} started bot")

async def daily(update: Update, context):
    await update.message.chat.send_action("typing")
    note = get_daily_note()
    await update.message.reply_text(f"📝 *Today's Note*\n\n{note}", parse_mode='Markdown')

async def allnotes(update: Update, context):
    await update.message.chat.send_action("typing")
    notes = get_all_notes()
    await update.message.reply_text(notes, parse_mode='Markdown')

async def questions(update: Update, context):
    await update.message.chat.send_action("typing")
    q = get_questions()
    await update.message.reply_text(q, parse_mode='Markdown')

async def answer(update: Update, context):
    if not context.args:
        await update.message.reply_text("Example: `/answer 1`", parse_mode='Markdown')
        return
    try:
        num = int(context.args[0])
        ans = get_answer(num)
        await update.message.reply_text(ans, parse_mode='Markdown')
    except:
        await update.message.reply_text("Please provide a valid number.")

async def books(update: Update, context):
    await update.message.chat.send_action("typing")
    books = get_books()
    await update.message.reply_text(books, parse_mode='Markdown')

async def ask(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "Example: `/ask What is photosynthesis?`",
            parse_mode='Markdown'
        )
        return
    
    question = ' '.join(context.args)
    await update.message.reply_text("🤔 Thinking...")
    response = await ask_gemini(question)
    await update.message.reply_text(f"💡 *Answer*\n\n{response}", parse_mode='Markdown')

async def error(update: Update, context):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ Something went wrong. Try again.")

# ============ MAIN ============

def main():
    print("=" * 40)
    print("🤖 EduBot Starting...")
    print("=" * 40)
    
    # Check credentials
    validate()
    
    # Create app
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("allnotes", allnotes))
    app.add_handler(CommandHandler("questions", questions))
    app.add_handler(CommandHandler("answer", answer))
    app.add_handler(CommandHandler("books", books))
    app.add_handler(CommandHandler("ask", ask))
    app.add_error_handler(error)
    
    # Start
    if WEBHOOK_URL:
        print(f"🚀 Webhook mode on port {PORT}")
        print(f"🌐 URL: {WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
        )
    else:
        print("🔄 Polling mode (local testing)")
        print("✅ Bot is running! Press Ctrl+C to stop.")
        app.run_polling()

if __name__ == "__main__":
    main()
