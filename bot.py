import logging
import os
from datetime import date
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client
import google.generativeai as genai

# ============================================
# YOUR CREDENTIALS - FILLED
# ============================================
BOT_TOKEN = "8755788296:AAEpumtdZTyIfvKGrl_tn6C2MleogO1LyKA"
SUPABASE_URL = "https://zecfvwgozgljqpmxfliv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplY2Z2d2dvemdsanFwbXhmbGl2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4NDU4NjUsImV4cCI6MjA5MDQyMTg2NX0.x4IxAt2lBTXsAT6pBZJyW_NL9hvzf3rUG-9EhziK7dE"
GEMINI_KEY = "AIzaSyDq_ZItv04bA-Nt7T0ycG5Bx1Ox3PMi4lg"
TEACHER_ID = "9eb32f57-8d2b-436e-91c8-e1cd0ad9ba89"

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ============ DATABASE FUNCTIONS ============

def save_student(telegram_user):
    """Save student to database"""
    try:
        data = {
            "telegram_id": telegram_user.id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "teacher_id": TEACHER_ID,
            "last_seen": date.today().isoformat()
        }
        supabase.table("students").upsert(data, on_conflict="telegram_id").execute()
        return True
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

def get_daily_note():
    """Get today's note"""
    try:
        today = date.today().isoformat()
        result = supabase.table("daily_notes") \
            .select("*") \
            .eq("teacher_id", TEACHER_ID) \
            .eq("note_date", today) \
            .eq("is_published", True) \
            .execute()
        if result.data:
            return result.data[0]["content"]
        return "📭 No note for today. Check back later!"
    except Exception as e:
        logger.error(f"Note error: {e}")
        return "Error fetching note"

def get_all_notes():
    """Get all notes"""
    try:
        result = supabase.table("daily_notes") \
            .select("title, content, note_date, subject") \
            .eq("teacher_id", TEACHER_ID) \
            .eq("is_published", True) \
            .order("note_date", desc=True) \
            .limit(10) \
            .execute()
        if not result.data:
            return "📭 No notes available"
        text = "📚 *Recent Notes*\n\n"
        for n in result.data:
            text += f"📅 **{n['note_date']}**\n"
            text += f"📝 {n['title']}\n"
            if n.get('subject'):
                text += f"📌 {n['subject']}\n"
            text += f"{n['content'][:100]}...\n\n"
        return text
    except Exception as e:
        return "Error fetching notes"

def get_questions():
    """Get practice questions"""
    try:
        result = supabase.table("questions") \
            .select("id, question_text, subject, difficulty") \
            .eq("teacher_id", TEACHER_ID) \
            .eq("is_active", True) \
            .limit(5) \
            .execute()
        if not result.data:
            return "📭 No questions available"
        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(result.data, 1):
            emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(q.get('difficulty'), "🟡")
            subject = f" [{q.get('subject', 'General')}]" if q.get('subject') else ""
            text += f"{i}. {emoji} {q['question_text']}{subject}\n\n"
        text += "\n💡 Type `/answer [number]` to see answer"
        return text
    except Exception as e:
        return "Error fetching questions"

def get_answer(num):
    """Get answer by number"""
    try:
        result = supabase.table("questions") \
            .select("question_text, answer, explanation") \
            .eq("teacher_id", TEACHER_ID) \
            .eq("is_active", True) \
            .limit(5) \
            .execute()
        if not result.data or num > len(result.data):
            return "❓ Question not found"
        q = result.data[num - 1]
        text = f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
        if q.get('explanation'):
            text += f"\n\n💡 *Explanation:* {q['explanation']}"
        return text
    except Exception as e:
        return "Error fetching answer"

def get_books():
    """Get all books"""
    try:
        result = supabase.table("books") \
            .select("title, author, file_url, subject") \
            .eq("teacher_id", TEACHER_ID) \
            .eq("is_active", True) \
            .execute()
        if not result.data:
            return "📭 No books available"
        text = "📚 *Available Books*\n\n"
        for b in result.data:
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
        await update.message.reply_text("Example: `/ask What is photosynthesis?`", parse_mode='Markdown')
        return
    question = ' '.join(context.args)
    await update.message.reply_text("🤔 Thinking...")
    try:
        response = model.generate_content(question)
        await update.message.reply_text(f"💡 *Answer*\n\n{response.text}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text("⚠️ AI busy. Try again in a moment.")

# ============ MAIN ============

def main():
    print("=" * 40)
    print("🤖 EduBot Starting on Railway...")
    print("=" * 40)
    
    port = int(os.environ.get("PORT", 8080))
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("allnotes", allnotes))
    app.add_handler(CommandHandler("questions", questions))
    app.add_handler(CommandHandler("answer", answer))
    app.add_handler(CommandHandler("books", books))
    app.add_handler(CommandHandler("ask", ask))
    
    # Get Railway URL for webhook
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    
    if railway_domain:
        webhook_url = f"https://{railway_domain}/{BOT_TOKEN}"
        print(f"🚀 Starting webhook: {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        print("🔄 Starting polling mode")
        app.run_polling()

if __name__ == "__main__":
    main()
