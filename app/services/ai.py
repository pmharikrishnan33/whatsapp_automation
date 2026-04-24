from app.config import GEMINI_API_KEY
import google.generativeai as genai
from app.services.memory import get_history

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")

def generate_replay(user_message: str, system_prompt: str, phone_number: str):
    history = get_history(phone_number)
    prompt = system_prompt + "\n"
    for msg in history:
        prompt += f"{msg['role']}: {msg['content']}\n"
    prompt += f"user: {user_message}"
    response = model.generate_content(prompt)
    return response.text