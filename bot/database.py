import logging
from datetime import date
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, TEACHER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

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
        logger.error(f"Save student error: {e}")
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
        logger.error(f"Get daily note error: {e}")
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
        logger.error(f"Get all notes error: {e}")
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
        logger.error(f"Get questions error: {e}")
        return "Error fetching questions"

def get_answer(num):
    """Get answer by question number"""
    try:
        result = supabase.table("questions") \
            .select("question_text, answer, explanation") \
            .eq("teacher_id", TEACHER_ID) \
            .eq("is_active", True) \
            .limit(5) \
            .execute()
        
        if not result.data or num > len(result.data):
            return "❓ Question not found. Use /questions to see available questions."
        
        q = result.data[num - 1]
        text = f"❓ *Question:* {q['question_text']}\n\n"
        text += f"✅ *Answer:* {q['answer']}"
        if q.get('explanation'):
            text += f"\n\n💡 *Explanation:* {q['explanation']}"
        return text
    except Exception as e:
        logger.error(f"Get answer error: {e}")
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
        logger.error(f"Get books error: {e}")
        return "Error fetching books"
