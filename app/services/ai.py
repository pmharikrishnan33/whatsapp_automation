from app.core.config import GEMINI_API_KEY
import google.generativeai as genai
from app.core.memory import get_history

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

# 1. Used for conversational chat (uses history)
def generate_replay(user_message: str, system_prompt: str, phone_number: str) -> str:
    history = get_history(phone_number)
    prompt = system_prompt + "\n\n"
    for msg in history:
        prompt += f"{msg['role']}: {msg['content']}\n"
    prompt += f"user: {user_message}"
    
    response = model.generate_content(prompt)
    return response.text.strip()

# 2. Used for utility tasks like receipts, summaries, or extraction (no history)
def run_custom_prompt(prompt_text: str) -> str:
    response = model.generate_content(prompt_text)
    return response.text.strip()