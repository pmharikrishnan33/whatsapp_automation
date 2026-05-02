import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def extract_price_rule_based(text: str):
    """Regex-based extraction for price signals."""
    patterns = [r'(?:under|below|less than|<=?)\s*(\d+)', r'(\d+)\s*(?:below|under)']
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match: return int(match.group(1))
    return None

def detect_category_signal(user_msg, client_data):
    """Maps keywords to categories."""
    categories_map = client_data.get("keywords", {}).get("categories", {})
    for category_name, synonyms in categories_map.items():
        for word in synonyms:
            if rf"\b{re.escape(word.lower())}\b" in user_msg.lower():
                return category_name
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    save_message_to_db(phone_number, "user", text, phone_number_id)
    user_msg_low = text.lower().strip()
    
    # 1. LOAD CONFIG
    features = client.get("features", {})
    ui_config = client.get("ui", {})
    keywords = client.get("keywords", {})
    
    # 2. SIGNAL COLLECTION
    detected_category = detect_category_signal(user_msg_low, client)
    max_price = extract_price_rule_based(user_msg_low)
    is_collection_req = any(w in user_msg_low for w in keywords.get("view_collection", []))
    is_greeting = any(w in user_msg_low for w in keywords.get("greeting", []))

    # 3. THE "BEST" LOGIC: PRIORITY ROUTING
    
    # CASE A: User ONLY said "Hi" (No other signals)
    if is_greeting and not (detected_category or max_price or is_collection_req):
        reply = client.get("intent_responses", {}).get("greeting")
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        return {"status": "greeting_sent"}

    # CASE B: User asked for Location or Size Guide (Manual early returns)
    for intent in ["location", "size_guide"]:
        if any(rf"\b{re.escape(w.lower())}\b" in user_msg_low for w in keywords.get(intent, [])):
            reply = client.get("intent_responses", {}).get(intent)
            send_whatsapp_message(phone_number, reply)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "manual_info_sent"}

    # CASE C: Catalog Logic (Triggered by Category, Price, or "Show Catalog")
    if features.get("catalog_enabled") and (detected_category or max_price or is_collection_req):
        all_products = client.get("products", [])
        filtered = [p for p in all_products if (not max_price or p['price'] <= max_price) and 
                    (not detected_category or p.get('category') == detected_category)]

        if filtered:
            body_text = f"👕 *{client.get('name')} Collection*\n"
            if max_price: body_text += f"_(Budget: {ui_config.get('currency')} {max_price})_\n"
            
            for i, prod in enumerate(filtered[:ui_config.get("max_items_per_message", 3)], 1):
                body_text += f"{i}. {prod['name']} - {ui_config.get('currency')} {prod['price']}\n"

            if features.get("buttons_enabled"):
                payload = {
                    "messaging_product": "whatsapp", "to": phone_number, "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "header": {"type": "image", "image": {"link": filtered[0]['image_url']}},
                        "body": {"text": body_text},
                        "action": {"buttons": [{"type": "reply", "reply": {"id": "select_1", "title": "Select #1"}},
                                               {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}]}
                    }
                }
                send_whatsapp_message(phone_number, payload)
            else:
                send_whatsapp_message(phone_number, body_text)
            return {"status": "catalog_sent"}

    # CASE D: Conversational Fallback (What is M? / I want something red)
    ai_reply = generate_replay(text, client.get("system_prompt"), phone_number)
    send_whatsapp_message(phone_number, ai_reply)
    save_message_to_db(phone_number, "assistant", ai_reply, phone_number_id)
    return {"status": "ai_reply_sent"}