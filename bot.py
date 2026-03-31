import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import requests
import json

# ============================================
# YOUR SUPABASE CREDENTIALS - VERIFIED
# ============================================
BOT_TOKEN = "8755788296:AAEpumtdZTyIfvKGrl_tn6C2MleogO1LyKA"
SUPABASE_URL = "https://zecfvwgozgljqpmxfliv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplY2Z2d2dvemdsanFwbXhmbGl2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4NDU4NjUsImV4cCI6MjA5MDQyMTg2NX0.x4IxAt2lBTXsAT6pBZJyW_NL9hvzf3rUG-9EhziK7dE"
TEACHER_ID = "9eb32f57-8d2b-436e-91c8-e1cd0ad9ba89"

# Gemini API Key (replace with your NEW key)
GEMINI_KEY = "YOUR_NEW_GEMINI_KEY_HERE"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
    logger.info("✅ Gemini initialized")
except Exception as e:
    logger.error(f"Gemini init error: {e}")
    model = None

# ============ SUPABASE FUNCTIONS ============

def supabase_query(endpoint, method="GET", data=None):
    """Query Supabase REST API"""
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
            logger.error(f"Supabase error {response.status_code}: {response.text[:200]}")
            return []
    except Exception as e:
        logger.error(f"Request error: {e}")
        return []

def test_supabase_connection():
    """Test if Supabase is accessible"""
    result = supabase_query("teachers?select=count&id=eq." + TEACHER_ID)
    if result:
        logger.info("✅ Supabase connected successfully")
        return True
    else:
        logger.error("❌ Supabase connection failed")
        return False

def get_daily_note():
    """Get today's note from Supabase"""
    try:
        today = date.today().isoformat()
        result = supabase_query(f"daily_notes?teacher_id=eq.{TEACHER_ID}&note_date=eq.{today}&select=content")
        if result and len(result) > 0:
            return result[0]["content"]
        return "📭 No note for today. Check back later!"
    except Exception as e:
        logger.error(f"Get daily note error: {e}")
        return "Error fetching note"

def get_all_notes():
    """Get all notes from Supabase"""
    try:
        result = supabase_query(f"daily_notes?teacher_id=eq.{TEACHER_ID}&order=note_date.desc&limit=10&select=title,content,note_date")
        if not result:
            return "📭 No notes available"
        
        text = "📚 *Recent Notes*\n\n"
        for n in result:
            text += f"📅 **{n['note_date']}**\n"
            text += f"📝 {n['title']}\n"
            text += f"{n['content'][:100]}...\n\n"
        return text
    except Exception as e:
        logger.error(f"Get all notes error: {e}")
        return "Error fetching notes"

def get_questions():
    """Get practice questions from Supabase"""
    try:
        result = supabase_query(f"questions?teacher_id=eq.{TEACHER_ID}&limit=5&select=id,question_text")
        if not result:
            return "📭 No questions available"
        
        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(result, 1):
            text += f"{i}. {q['question_text']}\n\n"
        text += "\n💡 Type `/answer [number]` to see answer"
        return text
    except Exception as e:
        logger.error(f"Get questions error: {e}")
        return "Error fetching questions"

def get_answer(num):
    """Get answer by number"""
    try:
        result = supabase_query(f"questions?teacher_id=eq.{TEACHER_ID}&limit=5&select=question_text,answer")
        if not result or num > len(result):
            return "❓ Question not found"
        
        q = result[num - 1]
        return f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
    except Exception as e:
        logger.error(f"Get answer error: {e}")
        return "Error fetching answer"

def get_books():
    """Get all books from Supabase"""
    try:
        result = supabase_query(f"books?teacher_id=eq.{TEACHER_ID}&select=title,author,file_url")
        if not result:
            return "📭 No books available"
        
        text = "📚 *Available Books*\n\n"
        for b in result:
            text += f"📖 **{b['title']}**\n"
            if b.get('author'):
                text += f"✍️ {b['author']}\n"
            if b.get('file_url'):
                text += f"🔗 [Link]({b['file_url']})\n"
            text += "\n"
        return text
    except Exception as e:
        logger.error(f"Get books error: {e}")
        return "Error fetching books"

def save_student(telegram_user):
    """Save student to Supabase"""
    try:
        # Check if student exists
        existing = supabase_query(f"students?telegram_id=eq.{telegram_user.id}&select=id")
        
        data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "teacher_id": TEACHER_ID
        }
        
        if existing and len(existing) > 0:
            # Update existing
            supabase_query(f"students?telegram_id=eq.{telegram_user.id}", "PATCH", data)
        else:
            # Insert new
            supabase_query("students", "POST", data)
        return True
    except Exception as e:
        logger.error(f"Save student error: {e}")
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
    
    text = f"""🎓 *Welcome {user.first_name}!*

I'm EduBot - your AI learning assistant.

Click the buttons below to get started! 🚀"""
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    logger.info(f"Student {user.id} started")

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "daily":
        note = get_daily_note()
        await query.message.reply_text(f"📝 *Today's Note*\n\n{note}", parse_mode='Markdown')
    
    elif action == "allnotes":
        notes = get_all_notes()
        await query.message.reply_text(notes, parse_mode='Markdown')
    
    elif action == "questions":
        q = get_questions()
        await query.message.reply_text(q, parse_mode='Markdown')
    
    elif action == "books":
        books = get_books()
        await query.message.reply_text(books, parse_mode='Markdown')
    
    elif action == "ask":
        await query.message.reply_text(
            "🤖 *Ask me anything!*\n\nType: `/ask What is love?`",
            parse_mode='Markdown'
        )

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
        await thinking.edit_text("⚠️ AI service not configured. Please contact administrator.")
        return
    
    try:
        response = model.generate_content(question)
        answer = response.text if response.text else "No response"
        
        if len(answer) > 4000:
            answer = answer[:4000] + "..."
        
        await thinking.edit_text(f"💡 *Answer:*\n\n{answer}", parse_mode='Markdown')
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "rate" in error_msg.lower():
            await thinking.edit_text("⚠️ AI is busy. Please wait a moment and try again.")
        elif "safety" in error_msg.lower():
            await thinking.edit_text("⚠️ I can't answer that question. Please ask something else.")
        else:
            await thinking.edit_text(f"⚠️ Error: {error_msg[:100]}")

async def error_handler(update: Update, context):
    logger.error(f"Error: {context.error}")

# ============ MAIN ============

def main():
    print("=" * 50)
    print("🤖 EduBot Starting...")
    print("=" * 50)
    
    # Test Supabase connection
    print("📡 Testing Supabase connection...")
    test_supabase_connection()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("answer", answer_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running!")
    print("Commands: /start, /ask, /answer")
    print("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
