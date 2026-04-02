import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import google.generativeai as genai
import requests

# ============================================
# GET CREDENTIALS FROM ENVIRONMENT VARIABLES
# ============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
TEACHER_ID = os.environ.get("TEACHER_ID")

# Validate credentials
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN not set in environment variables")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials not set")
if not GEMINI_KEY:
    raise Exception("❌ GEMINI_KEY not set")
if not TEACHER_ID:
    raise Exception("❌ TEACHER_ID not set")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini
model = None
try:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    logger.info("✅ Gemini initialized")
except Exception as e:
    logger.error(f"Gemini init error: {e}")

# ============================================
# DATABASE FUNCTIONS
# ============================================

def supabase_query(endpoint, method="GET", data=None):
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
        logger.error(f"Supabase error: {e}")
        return []

def get_student(telegram_id):
    result = supabase_query(f"students?telegram_id=eq.{telegram_id}&select=*,subject_id,grade_level_id")
    return result[0] if result else None

def save_student(telegram_user):
    existing = get_student(telegram_user.id)
    data = {
        "telegram_id": telegram_user.id,
        "username": telegram_user.username or "",
        "first_name": telegram_user.first_name or "",
        "teacher_id": TEACHER_ID
    }
    if existing:
        supabase_query(f"students?telegram_id=eq.{telegram_user.id}", "PATCH", data)
    else:
        supabase_query("students", "POST", data)

def update_student_subject(telegram_id, subject_id):
    supabase_query(f"students?telegram_id=eq.{telegram_id}", "PATCH", {"subject_id": subject_id})

def update_student_grade(telegram_id, grade_id):
    supabase_query(f"students?telegram_id=eq.{telegram_id}", "PATCH", {"grade_level_id": grade_id})

def get_subjects():
    return supabase_query(f"subjects?teacher_id=eq.{TEACHER_ID}&is_active=eq.true")

def get_grade_levels(subject_id):
    return supabase_query(f"grade_levels?teacher_id=eq.{TEACHER_ID}&subject_id=eq.{subject_id}&is_active=eq.true&order=order_index.asc")

def get_daily_note(subject_id=None, grade_id=None):
    try:
        query = f"daily_notes?teacher_id=eq.{TEACHER_ID}&is_published=eq.true&note_date=eq.{date.today().isoformat()}"
        if subject_id:
            query += f"&subject_id=eq.{subject_id}"
        if grade_id:
            query += f"&grade_level_id=eq.{grade_id}"
        result = supabase_query(query)
        if result:
            return result[0]
        return None
    except:
        return None

def get_questions(subject_id=None, grade_id=None, limit=5):
    query = f"questions?teacher_id=eq.{TEACHER_ID}&is_active=eq.true"
    if subject_id:
        query += f"&subject_id=eq.{subject_id}"
    if grade_id:
        query += f"&grade_level_id=eq.{grade_id}"
    query += f"&limit={limit}"
    return supabase_query(query)

def get_books(subject_id=None, grade_id=None):
    query = f"books?teacher_id=eq.{TEACHER_ID}&is_active=eq.true"
    if subject_id:
        query += f"&subject_id=eq.{subject_id}"
    if grade_id:
        query += f"&grade_level_id=eq.{grade_id}"
    return supabase_query(query)

def get_quizzes(subject_id=None, grade_id=None):
    query = f"quizzes?teacher_id=eq.{TEACHER_ID}&is_active=eq.true"
    if subject_id:
        query += f"&subject_id=eq.{subject_id}"
    if grade_id:
        query += f"&grade_level_id=eq.{grade_id}"
    return supabase_query(query)

def save_quiz_attempt(quiz_id, student_id, score, total, percentage):
    data = {
        "quiz_id": quiz_id,
        "student_id": student_id,
        "score": score,
        "total_points": total,
        "percentage": percentage
    }
    supabase_query("quiz_attempts", "POST", data)

# ============================================
# TELEGRAM HANDLERS
# ============================================

async def start(update: Update, context):
    user = update.effective_user
    save_student(user)
    
    keyboard = [
        [InlineKeyboardButton("📚 Select Subject", callback_data="select_subject")],
        [InlineKeyboardButton("🎓 Select Grade", callback_data="select_grade")],
        [InlineKeyboardButton("📝 Daily Note", callback_data="daily")],
        [InlineKeyboardButton("❓ Questions", callback_data="questions")],
        [InlineKeyboardButton("📖 Books", callback_data="books")],
        [InlineKeyboardButton("🎯 Take Quiz", callback_data="quizzes")],
        [InlineKeyboardButton("🤖 Ask AI", callback_data="ask")],
        [InlineKeyboardButton("📊 My Progress", callback_data="progress")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎓 *Welcome {user.first_name}!*\n\n"
        f"I'm EduBot - your AI learning assistant.\n\n"
        f"First, select your subject and grade level to get personalized content!\n\n"
        f"Click the buttons below to get started 🚀",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def select_subject(update: Update, context):
    subjects = get_subjects()
    if not subjects:
        await update.callback_query.message.reply_text("No subjects available yet.")
        return
    
    keyboard = []
    for subj in subjects:
        keyboard.append([InlineKeyboardButton(f"{subj.get('icon', '📚')} {subj['name']}", callback_data=f"subject_{subj['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back")])
    
    await update.callback_query.message.edit_text(
        "📚 *Select your subject:*\n\nChoose the subject you're studying:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def subject_selected(update: Update, context):
    query = update.callback_query
    subject_id = query.data.split('_')[1]
    
    context.user_data['subject_id'] = subject_id
    update_student_subject(query.from_user.id, subject_id)
    
    subjects = get_subjects()
    subject_name = next((s['name'] for s in subjects if s['id'] == subject_id), "Subject")
    
    await query.message.edit_text(
        f"✅ *Subject selected: {subject_name}*\n\n"
        f"Now select your grade level using the button below 👇",
        parse_mode='Markdown'
    )
    await select_grade(update, context)

async def select_grade(update: Update, context):
    subject_id = context.user_data.get('subject_id')
    if not subject_id:
        await update.callback_query.message.reply_text("Please select a subject first.")
        await select_subject(update, context)
        return
    
    grades = get_grade_levels(subject_id)
    if not grades:
        await update.callback_query.message.reply_text("No grade levels available for this subject yet.")
        return
    
    keyboard = []
    for grade in grades:
        emoji = "🎓" if grade.get('level_type') == 'college' else "📚"
        keyboard.append([InlineKeyboardButton(f"{emoji} {grade['name']}", callback_data=f"grade_{grade['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_subject")])
    
    await update.callback_query.message.edit_text(
        "🎓 *Select your grade/level:*\n\nChoose your current grade level:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def grade_selected(update: Update, context):
    query = update.callback_query
    grade_id = query.data.split('_')[1]
    
    context.user_data['grade_id'] = grade_id
    update_student_grade(query.from_user.id, grade_id)
    
    await query.message.edit_text(
        f"✅ *All set!*\n\n"
        f"Now you can use:\n"
        f"📝 /daily - Today's note\n"
        f"❓ /questions - Practice questions\n"
        f"📖 /books - Recommended books\n"
        f"🎯 /quiz - Take a quiz\n"
        f"🤖 /ask - Ask AI anything\n"
        f"📊 /progress - View your progress",
        parse_mode='Markdown'
    )

async def daily_note(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    subject_id = student.get('subject_id') if student else context.user_data.get('subject_id')
    grade_id = student.get('grade_level_id') if student else context.user_data.get('grade_id')
    
    note = get_daily_note(subject_id, grade_id)
    
    if note:
        await update.message.reply_text(
            f"📝 *Today's Note*\n\n"
            f"**{note['title']}**\n\n"
            f"{note['content']}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "📭 No note available for your subject and grade today.\n\n"
            "Check back later or select a different subject/grade using /start"
        )

async def questions_list(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    subject_id = student.get('subject_id') if student else context.user_data.get('subject_id')
    grade_id = student.get('grade_level_id') if student else context.user_data.get('grade_id')
    
    questions = get_questions(subject_id, grade_id)
    
    if questions:
        context.user_data['current_questions'] = questions
        
        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(questions, 1):
            difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(q.get('difficulty'), "🟡")
            text += f"{i}. {difficulty_emoji} {q['question_text']}\n\n"
        text += "💡 Type `/answer [number]` to see the answer"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("❓ No questions available for your selection yet.")

async def answer_command(update: Update, context):
    if not context.args:
        await update.message.reply_text("Example: `/answer 1`", parse_mode='Markdown')
        return
    
    try:
        num = int(context.args[0]) - 1
        questions = context.user_data.get('current_questions', [])
        
        if 0 <= num < len(questions):
            q = questions[num]
            response = f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
            if q.get('explanation'):
                response += f"\n\n💡 *Explanation:* {q['explanation']}"
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text("Question not found. Use /questions first.")
    except:
        await update.message.reply_text("Please provide a valid number.")

async def books_list(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    subject_id = student.get('subject_id') if student else context.user_data.get('subject_id')
    grade_id = student.get('grade_level_id') if student else context.user_data.get('grade_id')
    
    books = get_books(subject_id, grade_id)
    
    if books:
        text = "📚 *Recommended Books*\n\n"
        for b in books:
            text += f"📖 **{b['title']}**\n"
            if b.get('author'):
                text += f"✍️ {b['author']}\n"
            if b.get('file_url'):
                text += f"🔗 [Download/View]({b['file_url']})\n"
            text += "\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("📚 No books available for your selection yet.")

async def quizzes_list(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    subject_id = student.get('subject_id') if student else context.user_data.get('subject_id')
    grade_id = student.get('grade_level_id') if student else context.user_data.get('grade_id')
    
    quizzes = get_quizzes(subject_id, grade_id)
    
    if quizzes:
        keyboard = []
        for q in quizzes:
            keyboard.append([InlineKeyboardButton(f"📝 {q['title']}", callback_data=f"quiz_{q['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back")])
        
        await update.message.reply_text(
            "🎯 *Available Quizzes*\n\nSelect a quiz to start:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("🎯 No quizzes available for your selection yet.")

async def ask_ai(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "🤖 *Ask me anything!*\n\n"
            "Examples:\n"
            "/ask What is democracy?\n"
            "/ask Explain quantum physics\n"
            "/ask Help me understand algebra",
            parse_mode='Markdown'
        )
        return
    
    question = ' '.join(context.args)
    thinking_msg = await update.message.reply_text("🤔 Thinking...")
    
    if model is None:
        await thinking_msg.edit_text("⚠️ AI service is not configured. Please contact administrator.")
        return
    
    try:
        response = model.generate_content(question)
        
        if response and response.text:
            answer = response.text
            if len(answer) > 4000:
                answer = answer[:4000] + "..."
            await thinking_msg.edit_text(f"💡 *Answer:*\n\n{answer}", parse_mode='Markdown')
        else:
            await thinking_msg.edit_text("⚠️ Sorry, I couldn't generate an answer. Please try again.")
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        await thinking_msg.edit_text("⚠️ AI service is busy. Please try again in a moment.")

async def show_progress(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    if not student:
        await update.message.reply_text("Please setup your profile using /start first.")
        return
    
    attempts = supabase_query(f"quiz_attempts?student_id=eq.{student['id']}&order=completed_at.desc&limit=10")
    
    if attempts:
        text = "📊 *Your Learning Progress*\n\n"
        text += "*Recent Quiz Scores:*\n"
        for a in attempts:
            text += f"• Score: {a.get('score', 0)}/{a.get('total_points', 0)} ({a.get('percentage', 0)}%)\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(
            "📊 *Your Learning Progress*\n\n"
            "Take quizzes to see your progress! Use /quiz",
            parse_mode='Markdown'
        )

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "select_subject":
        await select_subject(update, context)
    elif query.data == "select_grade":
        await select_grade(update, context)
    elif query.data.startswith("subject_"):
        await subject_selected(update, context)
    elif query.data.startswith("grade_"):
        await grade_selected(update, context)
    elif query.data == "daily":
        await daily_note(update, context)
    elif query.data == "questions":
        await questions_list(update, context)
    elif query.data == "books":
        await books_list(update, context)
    elif query.data == "quizzes":
        await quizzes_list(update, context)
    elif query.data == "ask":
        await query.message.reply_text("Type: `/ask Your question here`", parse_mode='Markdown')
    elif query.data == "progress":
        await show_progress(update, context)
    elif query.data == "back":
        await start(update, context)
    elif query.data == "back_to_subject":
        await select_subject(update, context)

async def error_handler(update: Update, context):
    logger.error(f"Error: {context.error}")

# ============================================
# MAIN
# ============================================

def main():
    print("=" * 50)
    print("🤖 EduBot Starting...")
    print("=" * 50)
    print(f"BOT_TOKEN: {'✅ Set' if BOT_TOKEN else '❌ Missing'}")
    print(f"SUPABASE_URL: {'✅ Set' if SUPABASE_URL else '❌ Missing'}")
    print(f"SUPABASE_KEY: {'✅ Set' if SUPABASE_KEY else '❌ Missing'}")
    print(f"GEMINI_KEY: {'✅ Set' if GEMINI_KEY else '❌ Missing'}")
    print(f"TEACHER_ID: {'✅ Set' if TEACHER_ID else '❌ Missing'}")
    print(f"Gemini Model: {'✅ Ready' if model else '❌ Failed'}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily_note))
    app.add_handler(CommandHandler("questions", questions_list))
    app.add_handler(CommandHandler("answer", answer_command))
    app.add_handler(CommandHandler("books", books_list))
    app.add_handler(CommandHandler("quiz", quizzes_list))
    app.add_handler(CommandHandler("ask", ask_ai))
    app.add_handler(CommandHandler("progress", show_progress))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
