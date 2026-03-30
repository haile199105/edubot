import os

# ============================================
# YOUR CREDENTIALS - ALREADY FILLED
# ============================================
TELEGRAM_BOT_TOKEN = "8755788296:AAEpumtdZTyIfvKGrl_tn6C2MleogO1LyKA"
SUPABASE_URL = "https://zecfvwgozgljqpmxfliv.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InplY2Z2d2dvemdsanFwbXhmbGl2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4NDU4NjUsImV4cCI6MjA5MDQyMTg2NX0.x4IxAt2lBTXsAT6pBZJyW_NL9hvzf3rUG-9EhziK7dE"
GEMINI_API_KEY = "AIzaSyDq_ZItv04bA-Nt7T0ycG5Bx1Ox3PMi4lg"
TEACHER_ID = "9eb32f57-8d2b-436e-91c8-e1cd0ad9ba89"

# ============================================
# DEPLOYMENT SETTINGS
# ============================================
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", 10000))

def validate():
    """Check all credentials are present"""
    if not TELEGRAM_BOT_TOKEN:
        raise Exception("Missing TELEGRAM_BOT_TOKEN")
    if not SUPABASE_URL:
        raise Exception("Missing SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        raise Exception("Missing SUPABASE_SERVICE_KEY")
    if not GEMINI_API_KEY:
        raise Exception("Missing GEMINI_API_KEY")
    if not TEACHER_ID:
        raise Exception("Missing TEACHER_ID")
    print("✅ All credentials validated successfully!")
