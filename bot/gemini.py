import logging
import google.generativeai as genai
from config import GEMINI_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def ask_gemini(question):
    """Ask Gemini AI a question"""
    try:
        response = model.generate_content(question)
        if response.text:
            return response.text
        return "No response from AI"
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        error = str(e).lower()
        if "quota" in error or "rate" in error:
            return "⚠️ AI is busy. Please try again in a minute."
        return "⚠️ AI service unavailable. Please try again later."
