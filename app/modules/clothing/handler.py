import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def extract_price_signal(text: str):
    """Regex for budget filters without AI cost[cite: 1]."""
    patterns = [r'(?:under|below|less than|<=?)\s*(\d+)', r'(\d+)\s*(?:below|under)']
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match: return int(match.group(1))
    return None

def detect_category_signal(user_msg, client_data):
    """Uses Word Boundaries to avoid 'hi' vs 'shirt' conflict[cite: 1]."""
    categories_map = client_data.get("keywords", {}).get("categories", {})
    user_msg_low = user_msg.lower().strip()
    for category_name, synonyms in categories_map.items():
        for word in synonyms:
            if re.search(rf"\b{re.escape(word.lower())}\b", user_msg_low):
                return category_name
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    save_message_to_db(phone_number, "user", text, phone_number_id)
    user_msg_low = text.lower().strip()
    keywords = client.get("keywords", {})
    ui_config = client.get("ui", {})

    # Signal Collection
    detected_cat = detect_category_signal(user_msg_low, client)
    max_price = extract_price_signal(user_msg_low)
    is_greeting = any(re.search(rf"\b{re.escape(w.lower())}\b", user_msg_low) 
                      for w in keywords.get("greeting", []))

    # 1. Pure Greeting logic[cite: 1]
    if is_greeting and not (detected_cat or max_price):
        reply = client.get("intent_responses", {}).get("greeting")
        if reply:
            send_whatsapp_message(phone_number, reply)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "greeting_sent"}

    # 2. Catalog logic (Categories & Price)[cite: 1]
    if detected_cat or max_price:
        all_prods = client.get("products", [])
        filtered = [p for p in all_prods if 
                    (not detected_cat or p['category'] == detected_cat) and
                    (not max_price or p['price'] <= max_price)]

        if filtered:
            currency = ui_config.get("currency", "₹")
            body = f"👕 *{client.get('name')} Collection*\n"
            if max_price: body += f"_(Under {currency}{max_price})_\n"
            body += "__________________________\n\n"
            for i, p in enumerate(filtered[:3], 1):
                body += f"*{i}. {p['name']}*\n💰 {currency}{p['price']}\n📝 {p.get('description', '')}\n\n"
            
            send_whatsapp_message(phone_number, body)
            return {"status": "catalog_sent"}
        else:
            # Suggest available categories[cite: 1]
            avail = ", ".join(keywords.get("categories", {}).keys())
            reply = f"Not in stock. Try our available categories: *{avail}*"
            send_whatsapp_message(phone_number, reply)
            return {"status": "not_available"}

    # 3. AI Fallback
    ai_reply = generate_replay(text, client.get("system_prompt"), phone_number)
    send_whatsapp_message(phone_number, ai_reply)
    return {"status": "ai_reply_sent"}