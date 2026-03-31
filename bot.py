import logging
import os
from datetime import date
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai
import requests
import json

# ============================================
# YOUR CREDENTIALS - ALREADY FILLED
# ============================================
BOT_TOKEN = "8755788296:AAEpumtdZTyIfvKGrl_tn6C2MleogO1LyKA"
SUPABASE_URL = "https://zecfvwgozgljqpmxfliv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplY2Z2d2dvemdsanFwbXhmbGl2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4NDU4NjUsImV4cCI6MjA5MDQyMTg2NX0.x4IxAt2lBTXsAT6pBZJyW_NL9hvzf3rUG-9EhziK7dE"
GEMINI_KEY = "AIzaSyDq_ZItv04bA-Nt7T0ycG5Bx1Ox3PMi4lg"
TEACHER_ID = "9eb32f57-8d2b-436e-91c8-e1cd0ad9ba89"

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ============ SUPABASE FUNCTIONS (Using requests) ============

def supabase_request(endpoint, method="GET", data=None):
    """Make a request to Supabase REST API"""
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
            return None
        
        if response.status_code in [200, 201, 204]:
            return response.json() if response.content else []
        else:
            logger.error(f"Supabase error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Request error: {e}")
        return []

def save_student(telegram_user):
    """Save or update student in database"""
    try:
        # Check if student exists
        existing = supabase_request(f"students?telegram_id=eq.{telegram_user.id}&select=id")
        
        data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "teacher_id": TEACHER_ID,
            "last_seen": date.today().isoformat()
        }
        
        if existing and len(existing) > 0:
            # Update existing
            supabase_request(f"students?telegram_id=eq.{telegram_user.id}", "PATCH", data)
        else:
            # Insert new
            supabase_request("students", "POST", data)
        return True
    except Exception as e:
        logger.error(f"Save student error: {e}")
        return False

def get_daily_note():
    """Get today's note"""
    try:
        today = date.today().isoformat()
        result = supabase_request(f"daily_notes?teacher_id=eq.{TEACHER_ID}&note_date=eq.{today}&is_published=eq.true&select=content")
        if result and len(result) > 0:
            return result[0]["content"]
        return "📭 No note for today. Check back later!"
    except Exception as e:
        logger.error(f"Note error: {e}")
        return "Error fetching note"

def get_all_notes():
    """Get all notes"""
    try:
        result = supabase_request(f"daily_notes?teacher_id=eq.{TEACHER_ID}&is_published=eq.true&order=note_date.desc&limit=10&select=title,content,note_date,subject")
        if not result:
            return "📭 No notes available"
        
        text = "📚 *Recent Notes*\n\n"
        for n in result:
            text += f"📅 **{n['note_date']}**\n"
            text += f"📝 {n['title']}\n"
            if n.get('subject'):
                text += f"📌 {n['subject']}\n"
            text += f"{n['content'][:100]}...\n\n"
        return text
    except Exception as e:
        logger.error(f"Get notes error: {e}")
        return "Error fetching notes"

def get_questions():
    """Get practice questions"""
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
    except Exception as e:
        logger.error(f"Get questions error: {e}")
        return "Error fetching questions"

def get_answer(num):
    """Get answer by number"""
    try:
        result = supabase_request(f"questions?teacher_id=eq.{TEACHER_ID}&is_active=eq.true&limit=5&select=question_text,answer,explanation")
        if not result or num > len(result):
            return "❓ Question not found"
        
        q = result[num - 1]
        text = f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
        if q.get('explanation'):
            text += f"\n\n💡 *Explanation:* {q['explanation']}"
        return text
    except Exception as e:
        logger.error(f"Get answer error: {e}")
        return "Error fetching answer"

def get_books():
    """Get all books"""
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
    except Exception as e:
        logger.error(f"Get books error: {e}")
        return "Error fetching books"

# ============ TELEGRAM HANDLERS ============

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
    books_text = get_books()
    await update.message.reply_text(books_text, parse_mode='Markdown')

async def ask(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "Example: `/ask What is photosynthesis?`",
            parse_mode='Markdown'
        )
        return
    
    question = ' '.join(context.args)
    await update.message.reply_text("🤔 Thinking...")
    try:
        response = model.generate_content(question)
        await update.message.reply_text(f"💡 *Answer*\n\n{response.text}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        await update.message.reply_text("⚠️ AI busy. Try again in a moment.")

async def error_handler(update: Update, context):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ Something went wrong. Try again.")

# ============ MAIN ============

def main():
    print("=" * 40)
    print("🤖 EduBot Starting on Railway...")
    print("=" * 40)
    
    # Get port from Railway
    port = int(os.environ.get("PORT", 8080))
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("allnotes", allnotes))
    app.add_handler(CommandHandler("questions", questions))
    app.add_handler(CommandHandler("answer", answer))
    app.add_handler(CommandHandler("books", books))
    app.add_handler(CommandHandler("ask", ask))
    app.add_error_handler(error_handler)
    
    # Get Railway URL for webhook
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    
    if railway_domain:
        webhook_url = f"https://{railway_domain}/{BOT_TOKEN}"
        print(f"🚀 Starting webhook mode")
        print(f"🌐 Webhook URL: {webhook_url}")
        print(f"📡 Listening on port {port}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        print("🔄 Starting polling mode")
        print("✅ Bot is running!")
        app.run_polling()

if __name__ == "__main__":
    main()
