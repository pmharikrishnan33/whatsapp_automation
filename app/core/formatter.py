import re

def format_whatsapp_reply(text: str) -> str:
    # 1. Remove Markdown headers (### Header)
    text = re.sub(r'#+\s*', '', text)
    
    # 2. Convert Markdown bold (**text**) to WhatsApp bold (*text*)
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    
    # 3. Remove other Markdown artifacts like [links](url) but keep the URL
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1: \2', text)
    
    # 4. Ensure consistent line breaks (WhatsApp prefers \n\n for paragraphs)
    text = text.replace("\r\n", "\n").strip()
    
    return text