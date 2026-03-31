import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import google.generativeai as genai
import requests

# ============================================
# YOUR CREDENTIALS
# ============================================
BOT_TOKEN = "8755788296:AAEpumtdZTyIfvKGrl_tn6C2MleogO1LyKA"
SUPABASE_URL = "https://zecfvwgozgljqpmxfliv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplY2Z2d2dvemdsanFwbXhmbGl2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4NDU4NjUsImV4cCI6MjA5MDQyMTg2NX0.x4IxAt2lBTXsAT6pBZJyW_NL9hvzf3rUG-9EhziK7dE"
import os
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
TEACHER_ID = "9eb32f57-8d2b-436e-91c8-e1cd0ad9ba89"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Store teacher sessions (telegram_id -> teacher_id)
teacher_sessions = {}

# ============ SUPABASE FUNCTIONS ============

def supabase_request(endpoint, method="GET", data=None):
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
        return []
    except Exception as e:
        logger.error(f"Request error: {e}")
        return []

def authenticate_teacher(telegram_id, password):
    """Authenticate teacher using Telegram ID and password"""
    try:
        # Check if teacher exists with this telegram_id
        result = supabase_request(f"teachers?telegram_id=eq.{telegram_id}&select=id,name,email")
        if result and len(result) > 0:
            teacher_sessions[telegram_id] = result[0]["id"]
            return True, result[0]
        return False, None
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return False, None

def is_teacher(telegram_id):
    """Check if user is logged in as teacher"""
    return telegram_id in teacher_sessions

def save_student(telegram_user):
    """Save student to database"""
    try:
        existing = supabase_request(f"students?telegram_id=eq.{telegram_user.id}&select=id")
        data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "teacher_id": TEACHER_ID,
            "last_seen": date.today().isoformat(),
            "role": "student"
        }
        if existing and len(existing) > 0:
            supabase_request(f"students?telegram_id=eq.{telegram_user.id}", "PATCH", data)
        else:
            supabase_request("students", "POST", data)
        return True
    except Exception as e:
        logger.error(f"Save student error: {e}")
        return False

def get_daily_note():
    try:
        today = date.today().isoformat()
        result = supabase_request(f"daily_notes?teacher_id=eq.{TEACHER_ID}&note_date=eq.{today}&is_published=eq.true&select=content")
        if result and len(result) > 0:
            return result[0]["content"]
        return "📭 No note for today. Check back later!"
    except:
        return "Error fetching note"

def get_all_notes():
    try:
        result = supabase_request(f"daily_notes?teacher_id=eq.{TEACHER_ID}&is_published=eq.true&order=note_date.desc&limit=10&select=title,content,note_date,subject")
        if not result:
            return "📭 No notes available"
        text = "📚 *Recent Notes*\n\n"
        for n in result:
            text += f"📅 **{n['note_date']}**\n📝 {n['title']}\n"
            if n.get('subject'):
                text += f"📌 {n['subject']}\n"
            text += f"{n['content'][:100]}...\n\n"
        return text
    except:
        return "Error fetching notes"

def get_questions():
    try:
        result = supabase_request(f"questions?teacher_id=eq.{TEACHER_ID}&is_active=eq.true&limit=5&select=id,question_text,subject,difficulty")
        if not result:
            return "📭 No questions available"
        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(result, 1):
            emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(q.get('difficulty'), "🟡")
            subject = f" [{q.get('subject', 'General')}]" if q.get('subject') else ""
            text += f"{i}. {emoji} {q['question_text']}{subject}\n\n"
        text += "\n💡 Type `/answer [number]` to see answer"
        return text
    except:
        return "Error fetching questions"

def get_answer(num):
    try:
        result = supabase_request(f"questions?teacher_id=eq.{TEACHER_ID}&is_active=eq.true&limit=5&select=question_text,answer,explanation")
        if not result or num > len(result):
            return "❓ Question not found"
        q = result[num - 1]
        text = f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
        if q.get('explanation'):
            text += f"\n\n💡 *Explanation:* {q['explanation']}"
        return text
    except:
        return "Error fetching answer"

def get_books():
    try:
        result = supabase_request(f"books?teacher_id=eq.{TEACHER_ID}&is_active=eq.true&select=title,author,file_url,subject")
        if not result:
            return "📭 No books available"
        text = "📚 *Available Books*\n\n"
        for b in result:
            text += f"📖 **{b['title']}**\n"
            if b.get('author'):
                text += f"✍️ {b['author']}\n"
            if b.get('subject'):
                text += f"📌 {b['subject']}\n"
            if b.get('file_url'):
                text += f"🔗 [Access Link]({b['file_url']})\n"
            text += "\n"
        return text
    except:
        return "Error fetching books"

# ============ TEACHER FUNCTIONS ============

def add_note(title, subject, content, note_date):
    """Add a new note (teacher only)"""
    data = {
        "teacher_id": TEACHER_ID,
        "title": title,
        "subject": subject,
        "content": content,
        "note_date": note_date,
        "is_published": True
    }
    return supabase_request("daily_notes", "POST", data)

def add_question(question_text, answer, subject, difficulty):
    """Add a new question (teacher only)"""
    data = {
        "teacher_id": TEACHER_ID,
        "question_text": question_text,
        "answer": answer,
        "subject": subject,
        "difficulty": difficulty,
        "is_active": True
    }
    return supabase_request("questions", "POST", data)

def add_book(title, author, subject, description, file_url):
    """Add a new book (teacher only)"""
    data = {
        "teacher_id": TEACHER_ID,
        "title": title,
        "author": author,
        "subject": subject,
        "description": description,
        "file_url": file_url,
        "is_active": True
    }
    return supabase_request("books", "POST", data)

def get_students():
    """Get all students (teacher only)"""
    return supabase_request(f"students?teacher_id=eq.{TEACHER_ID}&select=first_name,username,telegram_id,joined_at")

# ============ TELEGRAM HANDLERS ============

async def start(update: Update, context):
    user = update.effective_user
    
    # Check if this is a teacher login attempt
    if context.args and context.args[0] == "teacher":
        await update.message.reply_text(
            "👨‍🏫 *Teacher Login*\n\n"
            "Please enter your 6-digit PIN to access teacher panel.\n\n"
            "Contact your administrator for your PIN.",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_pin'] = True
        return
    
    # Regular student start
    save_student(user)
    
    keyboard = [
        [InlineKeyboardButton("📝 Daily Note", callback_data="daily")],
        [InlineKeyboardButton("❓ Practice Questions", callback_data="questions")],
        [InlineKeyboardButton("🤖 Ask AI", callback_data="ask")],
        [InlineKeyboardButton("📚 Books", callback_data="books")],
        [InlineKeyboardButton("📋 All Notes", callback_data="allnotes")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🎓 *Welcome {user.first_name}!*

I'm EduBot - your AI learning assistant.

Click the buttons below to get started! 🚀"""
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    logger.info(f"Student {user.id} started bot")

async def handle_message(update: Update, context):
    user = update.effective_user
    text = update.message.text
    
    # Check if awaiting teacher PIN
    if context.user_data.get('awaiting_pin'):
        pin = text.strip()
        # For now, using a simple PIN (you can change this)
        if pin == "123456":
            teacher_sessions[user.id] = TEACHER_ID
            context.user_data['awaiting_pin'] = False
            context.user_data['is_teacher'] = True
            await show_teacher_panel(update)
        else:
            await update.message.reply_text("❌ Invalid PIN. Please try again or /start to cancel.")
        return
    
    # Regular message handling
    await update.message.reply_text("Please use the buttons below or type /start")

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
            "🤖 *Ask me anything!*\n\nType your question like this:\n`/ask What is love?`",
            parse_mode='Markdown'
        )
    
    elif action == "teacher_panel":
        if is_teacher(query.from_user.id):
            await show_teacher_panel(query)
        else:
            await query.message.reply_text("❌ You are not authorized. Use /start teacher to login.")

async def show_teacher_panel(update):
    """Show teacher panel with options"""
    keyboard = [
        [InlineKeyboardButton("📝 Add Daily Note", callback_data="add_note")],
        [InlineKeyboardButton("❓ Add Question", callback_data="add_question")],
        [InlineKeyboardButton("📚 Add Book", callback_data="add_book")],
        [InlineKeyboardButton("👨‍🎓 View Students", callback_data="view_students")],
        [InlineKeyboardButton("📊 View Stats", callback_data="view_stats")],
        [InlineKeyboardButton("🔓 Logout", callback_data="logout")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👨‍🏫 *Teacher Panel*\n\nWhat would you like to do?",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def ask(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "🤖 *Ask me anything!*\n\nExample: `/ask What is photosynthesis?`",
            parse_mode='Markdown'
        )
        return
    
    question = ' '.join(context.args)
    thinking = await update.message.reply_text("🤔 Thinking...")
    
    try:
        response = model.generate_content(question)
        answer = response.text if response.text else "No response generated"
        
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
    print("🤖 EduBot Starting on Railway...")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(MessageHandler(None, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    print("✅ EduBot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
