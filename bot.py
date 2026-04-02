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
if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, GEMINI_KEY, TEACHER_ID]):
    raise Exception("❌ Missing required environment variables")

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

def get_subjects_by_grade(grade_id):
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

def get_recommended_content(student_id):
    student = get_student(student_id)
    if not student:
        return []
    return get_questions(student.get('subject_id'), student.get('grade_level_id'), 3)

# ============================================
# MAIN MENU
# ============================================

async def start(update: Update, context):
    user = update.effective_user
    save_student(user)
    
    # Check if user has already selected grade and subject
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
            "I'm your AI learning assistant. Please wait while we set up your account...\n\n"
            "⚠️ No grade levels available yet. Please contact your teacher.",
            parse_mode='Markdown'
        )
        return
    
    # Group grades by type (secondary vs college)
    secondary_grades = [g for g in grades if g.get('level_type') == 'secondary']
    college_grades = [g for g in grades if g.get('level_type') == 'college']
    
    keyboard = []
    
    if secondary_grades:
        keyboard.append([InlineKeyboardButton("📚 Secondary School", callback_data="level_secondary")])
        for grade in secondary_grades[:6]:
            keyboard.append([InlineKeyboardButton(f"   📖 {grade['name']}", callback_data=f"grade_{grade['id']}")])
    
    if college_grades:
        keyboard.append([InlineKeyboardButton("🎓 College/University", callback_data="level_college")])
        for grade in college_grades:
            year_display = f"Year {grade['year']}" if grade.get('year') else grade['name']
            keyboard.append([InlineKeyboardButton(f"   🎓 {year_display}", callback_data=f"grade_{grade['id']}")])
    
    await update.message.reply_text(
        "🎓 *Welcome to EduBot!*\n\n"
        "I'm your personal AI learning assistant. Let me help you learn better!\n\n"
        "*Step 1:* Select your education level 👇",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def grade_selected(update: Update, context):
    query = update.callback_query
    grade_id = query.data.split('_')[1]
    
    context.user_data['selected_grade_id'] = grade_id
    update_student_grade(query.from_user.id, grade_id)
    
    # Get subjects for this grade
    subjects = get_subjects_by_grade(grade_id)
    
    if not subjects:
        await query.message.edit_text(
            "⚠️ No subjects available for this grade level yet.\n\n"
            "Please contact your teacher to add subjects.",
            parse_mode='Markdown'
        )
        return
    
    keyboard = []
    for subject in subjects:
        icon = subject.get('icon', '📚')
        keyboard.append([InlineKeyboardButton(f"{icon} {subject['name']}", callback_data=f"subject_{subject['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_grades")])
    
    await query.message.edit_text(
        "🎓 *Step 2:* Select your subject 👇\n\n"
        "Choose the subject you're studying:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def subject_selected(update: Update, context):
    query = update.callback_query
    subject_id = query.data.split('_')[1]
    
    context.user_data['selected_subject_id'] = subject_id
    update_student_subject(query.from_user.id, subject_id)
    
    await query.message.edit_text(
        "✅ *Setup Complete!*\n\n"
        "You're all set to start learning!\n\n"
        "Here's your personalized dashboard 👇",
        parse_mode='Markdown'
    )
    
    await show_main_menu(update, context)

# ============================================
# MAIN MENU (After Setup)
# ============================================

async def show_main_menu(update: Update, context):
    """Show main dashboard with all options"""
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    # Get recommended content
    recommendations = get_recommended_content(user_id)
    
    welcome_text = f"🎓 *Welcome back!*\n\n"
    welcome_text += f"📚 *Your Learning Path:*\n"
    
    if student:
        # Get grade and subject names
        grade = supabase_query(f"grade_levels?id=eq.{student.get('grade_level_id')}&select=name")
        subject = supabase_query(f"subjects?id=eq.{student.get('subject_id')}&select=name,icon")
        if grade:
            welcome_text += f"🎓 Grade: *{grade[0]['name']}*\n"
        if subject:
            welcome_text += f"📖 Subject: *{subject[0]['icon']} {subject[0]['name']}*\n"
    
    welcome_text += f"\n✨ *Quick Actions:*\n"
    
    keyboard = [
        [InlineKeyboardButton("📝 Today's Note", callback_data="daily")],
        [InlineKeyboardButton("❓ Practice Questions", callback_data="questions")],
        [InlineKeyboardButton("📚 Books", callback_data="books")],
        [InlineKeyboardButton("🎯 Take a Quiz", callback_data="quiz")],
        [InlineKeyboardButton("🤖 Ask AI Assistant", callback_data="ask_ai")],
        [InlineKeyboardButton("📋 All Notes", callback_data="all_notes")],
        [InlineKeyboardButton("📊 My Progress", callback_data="progress")],
        [InlineKeyboardButton("🔄 Change Subject/Grade", callback_data="change_settings")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    
    # Add recommendations if available
    if recommendations:
        welcome_text += f"\n💡 *Recommended for you:*\n"
        for i, rec in enumerate(recommendations[:2], 1):
            welcome_text += f"{i}. {rec['question_text'][:50]}...\n"
        keyboard.insert(2, [InlineKeyboardButton("⭐ Recommended Questions", callback_data="recommended")])
    
    await update.callback_query.message.edit_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================
# FEATURE HANDLERS
# ============================================

async def daily_note(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await update.callback_query.message.reply_text(
            "⚠️ Please set up your learning path first.\n\n"
            "Click 'Change Subject/Grade' to get started.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    note = get_daily_note(student.get('subject_id'), student.get('grade_level_id'))
    
    if note:
        text = f"📝 *Today's Note*\n\n"
        text += f"**{note['title']}**\n\n"
        text += note['content']
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await update.callback_query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.edit_text(
            "📭 *No note for today*\n\n"
            "Check back later or try a different subject.\n\n"
            "💡 Tip: Ask your teacher to add daily notes!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def all_notes(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await update.callback_query.message.reply_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    notes = get_all_notes(student.get('subject_id'), student.get('grade_level_id'))
    
    if notes:
        text = "📋 *All Notes*\n\n"
        for n in notes[:5]:
            text += f"📅 **{n['note_date']}** - {n['title']}\n"
            text += f"{n['content'][:100]}...\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await update.callback_query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.edit_text(
            "📭 *No notes available*\n\n"
            "Check back later for new content!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def practice_questions(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await update.callback_query.message.reply_text(
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
            keyboard.append([InlineKeyboardButton(f"📝 Show Answer #{i}", callback_data=f"show_answer_{i-1}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")])
        
        await update.callback_query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.edit_text(
            "❓ *No questions available*\n\n"
            "Check back later for new practice questions!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def show_answer(update: Update, context):
    query = update.callback_query
    index = int(query.data.split('_')[2])
    questions = context.user_data.get('current_questions', [])
    
    if 0 <= index < len(questions):
        q = questions[index]
        text = f"❓ *Question:* {q['question_text']}\n\n"
        text += f"✅ *Answer:* {q['answer']}\n"
        if q.get('explanation'):
            text += f"\n💡 *Explanation:* {q['explanation']}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Questions", callback_data="questions")]]
        await query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def books_list(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    if not student or not student.get('subject_id'):
        await update.callback_query.message.reply_text(
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
            if b.get('description'):
                text += f"📝 {b['description'][:100]}...\n"
            if b.get('file_url'):
                text += f"🔗 [Download/View]({b['file_url']})\n"
            text += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await update.callback_query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.edit_text(
            "📚 *No books available*\n\n"
            "Check back later for new resources!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

async def ask_ai_prompt(update: Update, context):
    await update.callback_query.message.edit_text(
        "🤖 *Ask Me Anything!*\n\n"
        "Type your question below and I'll help you learn.\n\n"
        "Examples:\n"
        "• Explain photosynthesis\n"
        "• What is the Pythagorean theorem?\n"
        "• Help me understand algebra\n\n"
        "Just type your question and send it!",
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
    await show_onboarding(update, context)

async def show_progress(update: Update, context):
    user_id = update.effective_user.id
    student = get_student(user_id)
    
    if not student:
        await update.callback_query.message.reply_text(
            "⚠️ Please set up your learning path first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Change Settings", callback_data="change_settings")]])
        )
        return
    
    # Get quiz attempts
    attempts = supabase_query(f"quiz_attempts?student_id=eq.{student['id']}&order=completed_at.desc&limit=10")
    
    text = "📊 *Your Learning Progress*\n\n"
    
    if student.get('grade_level_id'):
        grade = supabase_query(f"grade_levels?id=eq.{student['grade_level_id']}&select=name")
        if grade:
            text += f"🎓 *Grade:* {grade[0]['name']}\n"
    
    if student.get('subject_id'):
        subject = supabase_query(f"subjects?id=eq.{student['subject_id']}&select=name,icon")
        if subject:
            text += f"📖 *Subject:* {subject[0]['icon']} {subject[0]['name']}\n"
    
    text += f"\n📅 *Member since:* {student['enrolled_at'][:10] if student.get('enrolled_at') else 'Recently'}\n\n"
    
    if attempts:
        text += "*Recent Quiz Scores:*\n"
        for a in attempts:
            percentage = a.get('percentage', 0)
            emoji = "🎉" if percentage >= 80 else "👍" if percentage >= 60 else "📚"
            text += f"{emoji} Score: {a.get('score', 0)}/{a.get('total_points', 0)} ({percentage}%)\n"
    else:
        text += "📝 *No quiz attempts yet*\n"
        text += "Take your first quiz using the 'Take a Quiz' button!"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    await update.callback_query.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_help(update: Update, context):
    text = "❓ *EduBot Help Center*\n\n"
    text += "*What can I do?*\n"
    text += "📝 • Get daily learning notes\n"
    text += "❓ • Practice with questions\n"
    text += "📚 • Access recommended books\n"
    text += "🎯 • Take quizzes to test knowledge\n"
    text += "🤖 • Ask AI any question\n"
    text += "📊 • Track your progress\n\n"
    text += "*Need more help?*\n"
    text += "Contact your teacher for assistance!"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
    await update.callback_query.message.edit_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def recommended_content(update: Update, context):
    user_id = update.effective_user.id
    recommendations = get_recommended_content(user_id)
    
    if recommendations:
        text = "⭐ *Recommended for You*\n\n"
        for i, rec in enumerate(recommendations, 1):
            text += f"{i}. {rec['question_text']}\n"
            text += f"   ✅ Answer: {rec['answer']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]]
        await update.callback_query.message.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.callback_query.message.edit_text(
            "⭐ *No recommendations yet*\n\n"
            "Keep learning and we'll suggest content for you!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")]])
        )

# ============================================
# CALLBACK HANDLER
# ============================================

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu":
        await show_main_menu(update, context)
    elif query.data.startswith("grade_"):
        await grade_selected(update, context)
    elif query.data.startswith("subject_"):
        await subject_selected(update, context)
    elif query.data == "daily":
        await daily_note(update, context)
    elif query.data == "all_notes":
        await all_notes(update, context)
    elif query.data == "questions":
        await practice_questions(update, context)
    elif query.data.startswith("show_answer_"):
        await show_answer(update, context)
    elif query.data == "books":
        await books_list(update, context)
    elif query.data == "quiz":
        await update.callback_query.message.reply_text("🎯 Quiz feature coming soon!")
    elif query.data == "ask_ai":
        await ask_ai_prompt(update, context)
    elif query.data == "progress":
        await show_progress(update, context)
    elif query.data == "change_settings":
        await change_settings(update, context)
    elif query.data == "help":
        await show_help(update, context)
    elif query.data == "recommended":
        await recommended_content(update, context)
    elif query.data == "back_to_grades":
        await show_onboarding(update, context)

# ============================================
# MAIN
# ============================================

async def error_handler(update: Update, context):
    logger.error(f"Error: {context.error}")

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
    app.add_handler(CommandHandler("ask", handle_question))
    
    # Message handler for AI questions
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    
    # Callback handler for buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
