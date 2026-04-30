from app.core.config import GEMINI_API_KEY
import google.generativeai as genai
from app.core.memory import get_history

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

def generate_replay(user_message: str, system_prompt: str, phone_number: str):
    history = get_history(phone_number)
    prompt = system_prompt + "\n"
    for msg in history:
        prompt += f"{msg['role']}: {msg['content']}\n"
    prompt += f"user: {user_message}"
    response = model.generate_content(prompt)
    return response.text

def generate_receipt(user_text: str, menu_text: str) -> str:
    """Takes messy user input, matches it to the menu, fixes typos, and calculates the total."""
    prompt = f"""
    You are a highly accurate restaurant cashier AI. 
    The customer is ordering from this menu (which includes prices):
    {menu_text}
    
    The customer typed this messy text: "{user_text}"
    
    Task:
    1. Identify the items and quantities the customer wants. 
    2. Fix any spelling mistakes (e.g., if they say 'cladsic', map it to 'Classic Smash').
    3. Calculate the total price based on the menu provided.
    4. Return ONLY a clean, formatted receipt. Do not add conversational text like "Here is your receipt."
    
    Format example:
    1x The Classic Smash - ₹150
    2x Truffle Fries - ₹200
    ---
    Total: ₹350
    """
    
    response = model.generate_content(prompt)
    return response.text.strip()