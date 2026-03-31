import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import google.generativeai as genai
import requests

# ============================================
# GET CREDENTIALS FROM ENVIRONMENT VARIABLES (SECURE!)
# ============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
TEACHER_ID = os.environ.get("TEACHER_ID", "")

# Check if credentials are set
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not set in environment variables!")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Supabase credentials not set!")
if not GEMINI_KEY:
    print("❌ ERROR: GEMINI_KEY not set!")
if not TEACHER_ID:
    print("❌ ERROR: TEACHER_ID not set!")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini if key exists
model = None
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("✅ Gemini initialized")
    except Exception as e:
        logger.error(f"Gemini init error: {e}")

# ============ SUPABASE FUNCTIONS ============

def supabase_query(endpoint, method="GET", data=None):
    """Query Supabase REST API"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            return []
        
        if response.status_code in [200, 201, 204]:
            return response.json() if response.content else []
        else:
            logger.error(f"Supabase error {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Request error: {e}")
        return []

def get_daily_note():
    try:
        today = date.today().isoformat()
        result = supabase_query(f"daily_notes?teacher_id=eq.{TEACHER_ID}&note_date=eq.{today}&select=content")
        if result and len(result) > 0:
            return result[0]["content"]
        return "📭 No note for today. Check back later!"
    except:
        return "Error fetching note"

def get_all_notes():
    try:
        result = supabase_query(f"daily_notes?teacher_id=eq.{TEACHER_ID}&order=note_date.desc&limit=10&select=title,content,note_date")
        if not result:
            return "📭 No notes available"
        text = "📚 *Recent Notes*\n\n"
        for n in result:
            text += f"📅 **{n['note_date']}**\n📝 {n['title']}\n{n['content'][:100]}...\n\n"
        return text
    except:
        return "Error fetching notes"

def get_questions():
    try:
        result = supabase_query(f"questions?teacher_id=eq.{TEACHER_ID}&limit=5&select=id,question_text")
        if not result:
            return "📭 No questions available"
        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(result, 1):
            text += f"{i}. {q['question_text']}\n\n"
        text += "\n💡 Type `/answer [number]` to see answer"
        return text
    except:
        return "Error fetching questions"

def get_answer(num):
    try:
        result = supabase_query(f"questions?teacher_id=eq.{TEACHER_ID}&limit=5&select=question_text,answer")
        if not result or num > len(result):
            return "❓ Question not found"
        q = result[num - 1]
        return f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
    except:
        return "Error fetching answer"

def get_books():
    try:
        result = supabase_query(f"books?teacher_id=eq.{TEACHER_ID}&select=title")
        if not result:
            return "📭 No books available"
        text = "📚 *Available Books*\n\n"
        for b in result:
            text += f"📖 {b['title']}\n"
        return text
    except:
        return "Error fetching books"

def save_student(telegram_user):
    try:
        existing = supabase_query(f"students?telegram_id=eq.{telegram_user.id}&select=id")
        data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "teacher_id": TEACHER_ID
        }
        if existing and len(existing) > 0:
            supabase_query(f"students?telegram_id=eq.{telegram_user.id}", "PATCH", data)
        else:
            supabase_query("students", "POST", data)
        return True
    except:
        return False

# ============ TELEGRAM HANDLERS ============

async def start(update: Update, context):
    user = update.effective_user
    save_student(user)
    
    keyboard = [
        [InlineKeyboardButton("📝 Daily Note", callback_data="daily")],
        [InlineKeyboardButton("❓ Questions", callback_data="questions")],
        [InlineKeyboardButton("🤖 Ask AI", callback_data="ask")],
        [InlineKeyboardButton("📚 Books", callback_data="books")],
        [InlineKeyboardButton("📋 All Notes", callback_data="allnotes")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎓 *Welcome {user.first_name}!*\n\nI'm EduBot - your AI learning assistant.\n\nClick the buttons below! 🚀",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "daily":
        note = get_daily_note()
        await query.message.reply_text(f"📝 *Today's Note*\n\n{note}", parse_mode='Markdown')
    elif query.data == "allnotes":
        notes = get_all_notes()
        await query.message.reply_text(notes, parse_mode='Markdown')
    elif query.data == "questions":
        q = get_questions()
        await query.message.reply_text(q, parse_mode='Markdown')
    elif query.data == "books":
        books = get_books()
        await query.message.reply_text(books, parse_mode='Markdown')
    elif query.data == "ask":
        await query.message.reply_text("🤖 Ask me: `/ask What is love?`", parse_mode='Markdown')

async def answer_command(update: Update, context):
    if not context.args:
        await update.message.reply_text("Example: `/answer 1`", parse_mode='Markdown')
        return
    try:
        num = int(context.args[0])
        ans = get_answer(num)
        await update.message.reply_text(ans, parse_mode='Markdown')
    except:
        await update.message.reply_text("Please provide a valid number.")

async def ask_command(update: Update, context):
    if not context.args:
        await update.message.reply_text("Example: `/ask What is love?`", parse_mode='Markdown')
        return
    
    question = ' '.join(context.args)
    thinking = await update.message.reply_text("🤔 Thinking...")
    
    if model is None:
        await thinking.edit_text("⚠️ AI service not configured.")
        return
    
    try:
        response = model.generate_content(question)
        answer = response.text if response.text else "No response"
        if len(answer) > 4000:
            answer = answer[:4000] + "..."
        await thinking.edit_text(f"💡 *Answer:*\n\n{answer}", parse_mode='Markdown')
    except Exception as e:
        await thinking.edit_text(f"⚠️ Error: {str(e)[:100]}")

async def error_handler(update: Update, context):
    logger.error(f"Error: {context.error}")

# ============ MAIN ============

def main():
    print("=" * 50)
    print("🤖 EduBot Starting...")
    print("=" * 50)
    print(f"BOT_TOKEN: {'✅ Set' if BOT_TOKEN else '❌ Missing'}")
    print(f"SUPABASE_URL: {'✅ Set' if SUPABASE_URL else '❌ Missing'}")
    print(f"SUPABASE_KEY: {'✅ Set' if SUPABASE_KEY else '❌ Missing'}")
    print(f"GEMINI_KEY: {'✅ Set' if GEMINI_KEY else '❌ Missing'}")
    print(f"TEACHER_ID: {'✅ Set' if TEACHER_ID else '❌ Missing'}")
    print("=" * 50)
    
    if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERROR: Missing required credentials!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("answer", answer_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
