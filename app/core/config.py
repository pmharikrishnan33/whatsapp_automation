import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from the .env file
load_dotenv()

# Define these as standalone variables so they can be imported directly
MONGO_URI = os.getenv("MONGO_URI")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Global configuration for the AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)