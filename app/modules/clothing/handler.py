import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def extract_price_signal(text: str):
    """
    Regex to capture price signals (e.g., 'under 500') without AI cost.
    Handles 80-90% of pricing queries.
    """
    patterns = [
        r'(?:under|below|less than|<=?)\s*(\d+)',
        r'(\d+)\s*(?:below|under|thazhe)', 
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return int(match.group(1))
    return None

def detect_category_signal(user_msg, client_data):
    """
    Maps user synonyms (like 'tops') to internal categories (like 'shirt') 
    using the keywords.categories map from MongoDB.
    """
    categories_map = client_data.get("keywords", {}).get("categories", {})
    user_msg_low = user_msg.lower().strip()
    
    for category_name, synonyms in categories_map.items():
        for word in synonyms:
            if rf"\b{re.escape(word.lower())}\b" in user_msg_low:
                return category_name
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    """
    Main Handler: Collects signals -> Combines Filters -> Returns Catalog or AI Reply.
    """
    # 1. Persistent Logging
    save_message_to_db(phone_number, "user", text, phone_number_id)
    user_msg_low = text.lower().strip()
    
    # 2. Configuration & Signals
    features = client.get("features", {})
    ui_config = client.get("ui", {})
    keywords = client.get("keywords", {})
    
    detected_category = detect_category_signal(user_msg_low, client)
    max_price = extract_price_signal(user_msg_low)
    is_collection_req = any(w in user_msg_low for w in keywords.get("view_collection", []))
    is_greeting = any(w in user_msg_low for w in keywords.get("greeting", []))

    # 3. ROUTING LOGIC

    # CASE A: Pure Greeting (Prevents catalog spam on simple 'Hi')
    if is_greeting and not (detected_category or max_price or is_collection_req):
        reply = client.get("intent_responses", {}).get("greeting")
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        return {"status": "greeting_sent"}

    # CASE B: Informational (Location/Size)
    for intent in ["location", "size_guide"]:
        if any(rf"\b{re.escape(w.lower())}\b" in user_msg_low for w in keywords.get(intent, [])):
            reply = client.get("intent_responses", {}).get(intent)
            send_whatsapp_message(phone_number, reply)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "info_sent"}

    # CASE C: Filtered Catalog
    if features.get("catalog_enabled") and (detected_category or max_price or is_collection_req):
        all_products = client.get("products", [])
        
        # Combine category and price filters simultaneously
        filtered = [
            p for p in all_products 
            if (not max_price or p['price'] <= max_price) and 
               (not detected_category or p.get('category') == detected_category)
        ]

        if filtered:
            currency = ui_config.get("currency", "₹")
            max_items = ui_config.get("max_items_per_message", 3)
            
            body_text = f"👕 *{client.get('name')} Results*\n"
            if max_price: body_text += f"_(Budget: {currency}{max_price})_\n"
            body_text += "\n"
            
            for i, prod in enumerate(filtered[:max_items], 1):
                body_text += f"{i}. {prod['name']} - {currency}{prod['price']}\n"

            # Dynamic UI Choice: Buttons vs Plain Text
            if features.get("buttons_enabled"):
                catalog_payload = {
                    "messaging_product": "whatsapp",
                    "to": phone_number,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "header": {"type": "image", "image": {"link": filtered[0]['image_url']}},
                        "body": {"text": body_text},
                        "action": {
                            "buttons": [
                                {"type": "reply", "reply": {"id": "select_1", "title": "Select #1"}},
                                {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}
                            ]
                        }
                    }
                }
                send_whatsapp_message(phone_number, catalog_payload)
            else:
                send_whatsapp_message(phone_number, body_text)
            
            save_message_to_db(phone_number, "assistant", body_text, phone_number_id)
            return {"status": "catalog_sent"}

    # CASE D: Conversational Fallback (Uses Chat History)
    system_prompt = client.get("system_prompt", "You are Stitch, the fashion assistant.")
    ai_reply = generate_replay(text, system_prompt, phone_number)
    
    send_whatsapp_message(phone_number, ai_reply)
    save_message_to_db(phone_number, "assistant", ai_reply, phone_number_id)
    return {"status": "ai_reply_sent"}