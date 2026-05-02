import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def extract_price_signal(text: str):
    """Regex to capture price signals like 'under 500' without AI cost."""
    patterns = [
        r'(?:under|below|less than|<=?)\s*(\d+)',
        r'(\d+)\s*(?:below|under)', 
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return int(match.group(1))
    return None

def detect_category_signal(user_msg, client_data):
    """Maps synonyms to categories using Word Boundaries (\b) to avoid conflicts."""
    categories_map = client_data.get("keywords", {}).get("categories", {})
    user_msg_low = user_msg.lower().strip()
    
    for category_name, synonyms in categories_map.items():
        for word in synonyms:
            # Matches 'hi' as a word, but not inside 'shirt'
            if re.search(rf"\b{re.escape(word.lower())}\b", user_msg_low):
                return category_name
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Log incoming message to DB
    save_message_to_db(phone_number, "user", text, phone_number_id)
    user_msg_low = text.lower().strip()
    
    # 2. Configuration & Signals from MongoDB
    features = client.get("features", {})
    ui_config = client.get("ui", {})
    keywords = client.get("keywords", {})
    
    detected_category = detect_category_signal(user_msg_low, client)
    max_price = extract_price_signal(user_msg_low)
    
    is_collection_req = any(re.search(rf"\b{re.escape(w.lower())}\b", user_msg_low) 
                           for w in keywords.get("view_collection", []))
    is_greeting = any(re.search(rf"\b{re.escape(w.lower())}\b", user_msg_low) 
                      for w in keywords.get("greeting", []))

    # 3. ROUTING LOGIC

    # CASE A: Pure Greeting (No products mentioned)
    if is_greeting and not (detected_category or max_price or is_collection_req):
        reply = client.get("intent_responses", {}).get("greeting")
        if reply:
            send_whatsapp_message(phone_number, reply, phone_number_id)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "greeting_sent"}

    # CASE B: Informational (Location/Size)
    for intent in ["location", "size_guide"]:
        if any(re.search(rf"\b{re.escape(w.lower())}\b", user_msg_low) for w in keywords.get(intent, [])):
            reply = client.get("intent_responses", {}).get(intent)
            send_whatsapp_message(phone_number, reply, phone_number_id)
            return {"status": "info_sent"}

    # CASE C: Filtered Catalog
    if features.get("catalog_enabled") and (detected_category or max_price or is_collection_req):
        all_products = client.get("products", [])
        filtered = [
            p for p in all_products 
            if (not max_price or p['price'] <= max_price) and 
               (not detected_category or p.get('category') == detected_category)
        ]

        if filtered:
            currency = ui_config.get("currency", "₹")
            max_items = ui_config.get("max_items_per_message", 3)
            
            body_text = f"👕 *{client.get('name')} Selection*\n"
            if max_price: body_text += f"_(Budget: {currency}{max_price})_\n"
            body_text += "__________________________\n\n"
            
            for i, prod in enumerate(filtered[:max_items], 1):
                body_text += f"*{i}. {prod['name']}*\n"
                body_text += f"💰 Price: {currency}{prod['price']}\n"
                body_text += f"📝 {prod.get('description', 'High quality')}\n\n"

            # Use interactive buttons if enabled
            if features.get("buttons_enabled"):
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone_number,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "header": {"type": "image", "image": {"link": filtered[0]['image_url']}},
                        "body": {"text": body_text},
                        "action": {
                            "buttons": [{"type": "reply", "reply": {"id": "main", "title": "Main Menu"}}]
                        }
                    }
                }
                send_whatsapp_message(phone_number, payload, phone_number_id)
            else:
                send_whatsapp_message(phone_number, body_text, phone_number_id)
            return {"status": "catalog_sent"}
        else:
            # Suggest available categories if specific search fails
            avail_cats = ", ".join(keywords.get("categories", {}).keys())
            reply = f"Sorry, we don't have that in stock. Try these: *{avail_cats}*"
            send_whatsapp_message(phone_number, reply, phone_number_id)
            return {"status": "not_available"}

    # CASE D: AI Fallback
    ai_reply = generate_replay(text, client.get("system_prompt"), phone_number)
    send_whatsapp_message(phone_number, ai_reply, phone_number_id)
    return {"status": "ai_reply_sent"}