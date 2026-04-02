import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
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
    raise Exception("❌ BOT_TOKEN not set")
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

def update_student_grade(telegram_id, grade_id):
    supabase_query(f"students?telegram_id=eq.{telegram_id}", "PATCH", {"grade_level_id": grade_id})

def update_student_subject(telegram_id, subject_id):
    supabase_query(f"students?telegram_id=eq.{telegram_id}", "PATCH", {"subject_id": subject_id})

def get_grade_levels():
    return supabase_query(f"grade_levels?teacher_id=eq.{TEACHER_ID}&is_active=eq.true&order=order_index.asc")

def get_subjects():
    return supabase_query(f"subjects?teacher_id=eq.{TEACHER_ID}&is_active=eq.true")

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

def get_all_notes(subject_id=None, grade_id=None):
    query = f"daily_notes?teacher_id=eq.{TEACHER_ID}&is_published=eq.true&order=note_date.desc&limit=10"
    if subject_id:
        query += f"&subject_id=eq.{subject_id}"
    if grade_id:
        query += f"&grade_level_id=eq.{grade_id}"
    return supabase_query(query)

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

# ============================================
# HANDLERS
# ============================================

async def start(update: Update, context):
    user = update.effective_user
    save_student(user)
    
    student = get_student(user.id)
    
    if student and student.get('grade_level_id') and student.get('subject_id'):
        await show_main_menu(update, context)
    else:
        await show_onboarding(update, context)

async def show_onboarding(update: Update, context):
    """Step 1: Ask for grade level"""
    grades = get_grade_levels()
    
    if not grades:
        await update.message.reply_text(
            "📚 *Welcome to EduBot!*\n\n"
            "⚠️ No grade levels available yet. Please contact your teacher.",
            parse_mode='Markdown'
        )
        return
    
    keyboard = []
    for grade in grades:
        emoji = "🎓" if grade.get('level_type') == 'college' else "📚"
        keyboard.append([InlineKeyboardButton(f"{emoji} {grade['name']}", callback_data=f"grade_{grade['id']}")])
    
    await update.message.reply_text(
        "🎓 *Welcome to EduBot!*\n\n"
        "I'm your personal AI learning assistant.\n\n"
        "*Step 1:* Select your grade/level 👇",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def grade_selected(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    grade_id = query.data.split('_')[1]
    context.user_data['selected_grade_id'] = grade_id
    update_student_grade(query.from_user.id, grade_id)
    
    subjects = get_subjects()
    
    if not subjects:
        await query.message.edit_text(
            "⚠️ No subjects available yet.\n\nPlease contact your teacher.",
            parse_mode='Markdown'
        )
        return
    
    keyboard = []
    for subject in subjects:
        icon = subject.get('icon', '📚')
        keyboard.append([InlineKeyboardButton(f"{icon} {subject['name']}", callback_data=f"subject_{subject['id']}")])
    
    await query.message.edit_text(
        "🎓 *Step 2:* Select your subject 👇",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def subject_selected(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    subject_id = query.data.split('_')[1]
    context.user_data['selected_subject_id'] = subject_id
    update_student_subject(query.from_user.id, subject_id)
    
    await query.message.edit_text(
        "✅ *Setup Complete!*\n\n"
        "Here's your personalized dashboard 👇",
        parse_mode='Markdown'
    )
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context):
    """Main menu after setup"""
    user_id = update.effective_user.id
    
    # Check if this is from callback or direct message
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message
    
    student = get_student(user_id)
    
    welcome_text = f"🎓 *Welcome to EduBot!*\n\n"
    
    if student:
        grade = supabase_query(f"grade_levels?id=eq.{student.get('grade_level_id')}&select=name")
        subject = supabase_query(f"subjects?id=eq.{student.get('subject_id')}&select=name,icon")
        if grade:
            welcome_text += f"📚 Grade: *{grade[0]['name']}*\n"
        if subject:
            welcome_text += f"📖 Subject: *{subject[0]['icon']} {subject[0]['name']}*\n"
    
    welcome_text += f"\n✨ *What would you like to do?* ✨\n"
    
    keyboard = [
        [InlineKeyboardButton("📝 Today's Note", callback_data="daily")],
        [InlineKeyboardButton("❓ Practice Questions", callback_data="questions")],
        [InlineKeyboardButton("📚 Books", callback_data="books")],
        [InlineKeyboardButton("🤖 Ask AI Assistant", callback_data="ask_ai")],
        [InlineKeyboardButton("📋 All Notes", callback_data="all_notes")],
        [InlineKeyboardButton("📊 My Progress", callback_data="progress")],
        [InlineKeyboardButton("🔄 Change Settings", callback_data="change_settings")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await message.edit_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

async def daily_note(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await query.message.edit_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    note = get_daily_note(student.get('subject_id'), student.get('grade_level_id'))
    
    if note:
        text = f"📝 *Today's Note*\n\n**{note['title']}**\n\n{note['content']}"
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.edit_text(
            "📭 *No note for today*\n\nCheck back later!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def all_notes(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await query.message.edit_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    notes = get_all_notes(student.get('subject_id'), student.get('grade_level_id'))
    
    if notes:
        text = "📋 *All Notes*\n\n"
        for n in notes[:5]:
            text += f"📅 **{n['note_date']}** - {n['title']}\n{n['content'][:100]}...\n\n"
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.edit_text(
            "📭 *No notes available*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def practice_questions(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await query.message.edit_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    questions = get_questions(student.get('subject_id'), student.get('grade_level_id'))
    
    if questions:
        context.user_data['current_questions'] = questions
        
        text = "❓ *Practice Questions*\n\n"
        for i, q in enumerate(questions, 1):
            difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(q.get('difficulty'), "🟡")
            text += f"{i}. {difficulty_emoji} {q['question_text']}\n\n"
        
        keyboard = []
        for i, q in enumerate(questions, 1):
            keyboard.append([InlineKeyboardButton(f"📝 Show Answer #{i}", callback_data=f"answer_{i-1}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")])
        
        await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.edit_text(
            "❓ *No questions available*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def show_answer(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    index = int(query.data.split('_')[1])
    questions = context.user_data.get('current_questions', [])
    
    if 0 <= index < len(questions):
        q = questions[index]
        text = f"❓ *Question:* {q['question_text']}\n\n✅ *Answer:* {q['answer']}"
        if q.get('explanation'):
            text += f"\n\n💡 *Explanation:* {q['explanation']}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Questions", callback_data="questions")]]
        await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def books_list(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await query.message.edit_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    books = get_books(student.get('subject_id'), student.get('grade_level_id'))
    
    if books:
        text = "📚 *Recommended Books*\n\n"
        for b in books:
            text += f"📖 **{b['title']}**\n"
            if b.get('author'):
                text += f"✍️ {b['author']}\n"
            if b.get('file_url'):
                text += f"🔗 [Download]({b['file_url']})\n"
            text += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.edit_text(
            "📚 *No books available*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def ask_ai_prompt(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🤖 *Ask Me Anything!*\n\n"
        "Type your question below and I'll help you learn.\n\n"
        "Examples:\n"
        "• Explain photosynthesis\n"
        "• What is the Pythagorean theorem?\n"
        "• Help me understand algebra\n\n"
        "Just type your question!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
    )
    context.user_data['awaiting_question'] = True

async def handle_question(update: Update, context):
    if not context.user_data.get('awaiting_question'):
        return
    
    question = update.message.text
    context.user_data['awaiting_question'] = False
    
    thinking_msg = await update.message.reply_text("🤔 Thinking...")
    
    if model is None:
        await thinking_msg.edit_text("⚠️ AI service is not configured.")
        return
    
    try:
        response = model.generate_content(question)
        
        if response and response.text:
            answer = response.text
            if len(answer) > 4000:
                answer = answer[:4000] + "..."
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
            await thinking_msg.delete()
            await update.message.reply_text(
                f"💡 *Answer:*\n\n{answer}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await thinking_msg.edit_text("⚠️ Sorry, I couldn't generate an answer.")
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        await thinking_msg.edit_text("⚠️ AI service is busy. Please try again in a moment.")

async def change_settings(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await show_onboarding(update, context)

async def show_progress(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    student = get_student(user_id)
    
    if not student:
        await query.message.edit_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    text = "📊 *Your Learning Progress*\n\n"
    
    if student.get('grade_level_id'):
        grade = supabase_query(f"grade_levels?id=eq.{student['grade_level_id']}&select=name")
        if grade:
            text += f"🎓 Grade: {grade[0]['name']}\n"
    
    if student.get('subject_id'):
        subject = supabase_query(f"subjects?id=eq.{student['subject_id']}&select=name,icon")
        if subject:
            text += f"📖 Subject: {subject[0]['icon']} {subject[0]['name']}\n"
    
    text += f"\n📅 Started: {student['enrolled_at'][:10] if student.get('enrolled_at') else 'Recently'}\n\n"
    text += "💡 Keep learning! Take quizzes and answer questions to see your progress here."
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_help(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    text = "❓ *EduBot Help*\n\n"
    text += "*What can I do?*\n"
    text += "📝 Get daily notes\n"
    text += "❓ Practice questions\n"
    text += "📚 Access books\n"
    text += "🤖 Ask AI any question\n"
    text += "📋 View all notes\n"
    text += "📊 Track progress\n\n"
    text += "Contact your teacher for more help!"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# CALLBACK HANDLER
# ============================================

async def button_callback(update: Update, context):
    query = update.callback_query
    data = query.data
    
    if data == "menu":
        await show_main_menu(update, context)
    elif data.startswith("grade_"):
        await grade_selected(update, context)
    elif data.startswith("subject_"):
        await subject_selected(update, context)
    elif data == "daily":
        await daily_note(update, context)
    elif data == "all_notes":
        await all_notes(update, context)
    elif data == "questions":
        await practice_questions(update, context)
    elif data.startswith("answer_"):
        await show_answer(update, context)
    elif data == "books":
        await books_list(update, context)
    elif data == "ask_ai":
        await ask_ai_prompt(update, context)
    elif data == "progress":
        await show_progress(update, context)
    elif data == "change_settings":
        await change_settings(update, context)
    elif data == "help":
        await show_help(update, context)

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
    print(f"Gemini: {'✅ Ready' if model else '❌ Failed'}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    
    # Message handler for AI questions
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    
    # Callback handler for buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running! Waiting for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
