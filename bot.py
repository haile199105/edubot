import logging
import os
from datetime import date
from typing import Optional, Dict, Any

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import google.generativeai as genai

# ============================================
# CONFIGURATION & LOGGING
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('edubot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables with validation
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
GEMINI_KEY: str = os.getenv("GEMINI_KEY", "")
TEACHER_ID: str = os.getenv("TEACHER_ID", "")

# Validate critical credentials
missing = []
if not BOT_TOKEN: missing.append("BOT_TOKEN")
if not SUPABASE_URL: missing.append("SUPABASE_URL")
if not SUPABASE_KEY: missing.append("SUPABASE_KEY")
if not GEMINI_KEY: missing.append("GEMINI_KEY")
if not TEACHER_ID: missing.append("TEACHER_ID")

if missing:
    logger.critical(f"Missing required environment variables: {', '.join(missing)}")
    raise SystemExit("❌ Critical credentials missing. Please set environment variables.")

# Initialize Gemini
model = None
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    logger.info("✅ Gemini AI initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini: {e}")
    model = None

# ============================================
# SUPABASE HELPER CLASS (More Professional)
# ============================================
class SupabaseClient:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def query(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        try:
            full_url = f"{self.url}/rest/v1/{endpoint}"
            
            if method == "GET":
                response = requests.get(full_url, headers=self.headers, params=params)
            elif method == "POST":
                response = requests.post(full_url, headers=self.headers, json=data)
            elif method == "PATCH":
                response = requests.patch(full_url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = requests.delete(full_url, headers=self.headers)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None

            if response.status_code in (200, 201, 204):
                return response.json() if response.content else []
            else:
                logger.error(f"Supabase {method} error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Supabase request failed: {e}")
            return None


supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# DATABASE FUNCTIONS
# ============================================
def get_daily_note() -> str:
    try:
        today = date.today().isoformat()
        params = {"teacher_id": f"eq.{TEACHER_ID}", "note_date": f"eq.{today}", "select": "content"}
        result = supabase.query("daily_notes", params=params)
        
        if result and len(result) > 0:
            return result[0].get("content", "No content available.")
        return "📭 No daily note available for today.\nCheck back tomorrow!"
    except Exception as e:
        logger.error(f"Error fetching daily note: {e}")
        return "⚠️ Unable to fetch today's note. Please try again later."


def get_all_notes() -> str:
    try:
        params = {
            "teacher_id": f"eq.{TEACHER_ID}",
            "order": "note_date.desc",
            "limit": "10",
            "select": "title,content,note_date"
        }
        result = supabase.query("daily_notes", params=params)
        
        if not result:
            return "📭 No notes available yet."

        text = "📚 *Recent Learning Notes*\n\n"
        for note in result:
            content_preview = note.get('content', '')[:120] + "..." if len(note.get('content', '')) > 120 else note.get('content', '')
            text += f"📅 *{note.get('note_date')}*\n" \
                    f"📝 {note.get('title')}\n" \
                    f"{content_preview}\n\n"
        return text
    except Exception as e:
        logger.error(f"Error fetching all notes: {e}")
        return "⚠️ Error loading notes."


def get_questions() -> str:
    try:
        params = {
            "teacher_id": f"eq.{TEACHER_ID}",
            "limit": "5",
            "select": "id,question_text"
        }
        result = supabase.query("questions", params=params)
        
        if not result:
            return "📭 No practice questions available yet."

        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(result, 1):
            text += f"{i}. {q.get('question_text')}\n\n"
        text += "💡 Reply with `/answer 1` to see the answer."
        return text
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        return "⚠️ Error loading questions."


def get_answer(num: int) -> str:
    try:
        params = {
            "teacher_id": f"eq.{TEACHER_ID}",
            "limit": "10",
            "select": "question_text,answer"
        }
        result = supabase.query("questions", params=params)
        
        if not result or num < 1 or num > len(result):
            return "❓ Question number not found."

        q = result[num - 1]
        return f"❓ *Question:*\n{q.get('question_text')}\n\n" \
               f"✅ *Answer:*\n{q.get('answer')}"
    except Exception as e:
        logger.error(f"Error fetching answer: {e}")
        return "⚠️ Error retrieving answer."


def get_books() -> str:
    try:
        params = {"teacher_id": f"eq.{TEACHER_ID}", "select": "title,author"}
        result = supabase.query("books", params=params)
        
        if not result:
            return "📭 No books available yet."

        text = "📚 *Available Books*\n\n"
        for book in result:
            author = f" — {book.get('author')}" if book.get('author') else ""
            text += f"📖 *{book.get('title')}*{author}\n"
        return text
    except Exception as e:
        logger.error(f"Error fetching books: {e}")
        return "⚠️ Error loading books."


def save_student(telegram_user) -> bool:
    try:
        data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "teacher_id": TEACHER_ID
        }
        
        # Check if student exists
        existing = supabase.query(f"students?telegram_id=eq.{telegram_user.id}&select=id")
        
        if existing and len(existing) > 0:
            supabase.query(f"students?telegram_id=eq.{telegram_user.id}", "PATCH", data)
        else:
            supabase.query("students", "POST", data)
        
        return True
    except Exception as e:
        logger.error(f"Error saving student: {e}")
        return False


# ============================================
# TELEGRAM HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_student(user)

    keyboard = [
        [InlineKeyboardButton("📝 Daily Note", callback_data="daily")],
        [InlineKeyboardButton("📋 All Notes", callback_data="allnotes")],
        [InlineKeyboardButton("❓ Practice Questions", callback_data="questions")],
        [InlineKeyboardButton("📚 Books", callback_data="books")],
        [InlineKeyboardButton("🤖 Ask AI", callback_data="ask")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎓 *Welcome back, {user.first_name}!*\n\n"
        "I'm your personal AI learning assistant.\n"
        "Choose an option below to start learning:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "daily":
        note = get_daily_note()
        await query.message.reply_text(f"📝 *Today's Daily Note*\n\n{note}", parse_mode='Markdown')

    elif query.data == "allnotes":
        notes = get_all_notes()
        await query.message.reply_text(notes, parse_mode='Markdown')

    elif query.data == "questions":
        questions = get_questions()
        await query.message.reply_text(questions, parse_mode='Markdown')

    elif query.data == "books":
        books = get_books()
        await query.message.reply_text(books, parse_mode='Markdown')

    elif query.data == "ask":
        await query.message.reply_text(
            "🤖 *Ask me anything!*\n\n"
            "Just type:\n`/ask Your question here`",
            parse_mode='Markdown'
        )


async def answer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/answer 1`\n\nExample: `/answer 3`",
            parse_mode='Markdown'
        )
        return

    try:
        num = int(context.args[0])
        answer_text = get_answer(num)
        await update.message.reply_text(answer_text, parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number after /answer")
    except Exception as e:
        logger.error(f"Answer command error: {e}")
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/ask Your question`\n\nExample: `/ask Explain photosynthesis`",
            parse_mode='Markdown'
        )
        return

    question = " ".join(context.args).strip()
    thinking_msg = await update.message.reply_text("🤔 Thinking...")

    if model is None:
        await thinking_msg.edit_text("⚠️ AI service is currently unavailable.")
        return

    try:
        response = model.generate_content(question)
        answer = response.text.strip() if hasattr(response, 'text') and response.text else "Sorry, I couldn't generate a response."

        # Truncate if too long for Telegram
        if len(answer) > 3800:
            answer = answer[:3800] + "\n\n... (message too long)"

        await thinking_msg.edit_text(f"💡 *Answer:*\n\n{answer}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        await thinking_msg.edit_text("⚠️ Sorry, the AI is having trouble responding right now. Please try again later.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling update: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ An unexpected error occurred. Our team has been notified.")


# ============================================
# MAIN
# ============================================
def main():
    logger.info("🚀 Starting EduBot v2.0 - Professional Edition")

    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("answer", answer_command))
    app.add_handler(CommandHandler("ask", ask_command))

    # Button callback
    app.add_handler(CallbackQueryHandler(button_callback))

    # Error handler
    app.add_error_handler(error_handler)

    logger.info("✅ Bot handlers registered successfully")
    logger.info("🤖 EduBot is now polling...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
