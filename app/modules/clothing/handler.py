import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def extract_price_rule_based(text: str):
    """Regex-based extraction to handle 90% of price queries for FREE."""
    patterns = [
        r'(?:under|below|less than|lower than|<=?)\s*(\d+)',
        r'(\d+)\s*(?:below|under|thazhe)', 
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return int(match.group(1))
    return None

def detect_category_signal(user_msg, client_data):
    """Checks the categories dictionary in keywords to find a match."""
    categories_map = client_data.get("keywords", {}).get("categories", {})
    user_msg = user_msg.lower().strip()
    
    for category_name, synonyms in categories_map.items():
        for word in synonyms:
            if rf"\b{re.escape(word.lower())}\b" in user_msg:
                return category_name
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Log incoming message
    save_message_to_db(phone_number, "user", text, phone_number_id)
    user_msg_low = text.lower().strip()
    
    # 2. LOAD FEATURE FLAGS & UI CONFIG
    features = client.get("features", {})
    ui_config = client.get("ui", {})
    
    # 3. SIGNAL COLLECTION
    detected_category = detect_category_signal(user_msg_low, client)
    max_price = extract_price_rule_based(user_msg_low)
    
    # Identify if it's a general collection request
    is_collection_request = any(w in user_msg_low for w in client.get("keywords", {}).get("view_collection", []))

    # 4. AI FALLBACK (Only if features allow and signals are missing)
    if features.get("ai_fallback") and not (detected_category or max_price):
        if len(user_msg_low) > 10: # Only trigger AI for longer, complex phrases
            ai_query = f"{CLOTHING_SYSTEM_PROMPT}\n\nUser Message: {text}"
            ai_raw = run_custom_prompt(ai_query)
            try:
                ai_data = json.loads(ai_raw.replace('```json', '').replace('```', '').strip())
                max_price = max_price or ai_data.get("max_price")
                if ai_data.get("intent") in ["SHOW_PRODUCTS", "FILTER_PRICE"]:
                    is_collection_request = True
            except:
                pass

    # 5. EXECUTE FILTERED CATALOG LOGIC
    if features.get("catalog_enabled") and (detected_category or max_price or is_collection_request or user_msg_low == "hi"):
        all_products = client.get("products", [])
        
        # Filter products based on signals
        filtered = all_products
        if max_price:
            filtered = [p for p in filtered if p['price'] <= max_price]
        if detected_category:
            filtered = [p for p in filtered if p.get('category') == detected_category]

        if filtered:
            # Build Text Body
            currency = ui_config.get("currency", "₹")
            max_items = ui_config.get("max_items_per_message", 3)
            
            body_text = f"👕 *{client.get('name')} Collection*\n"
            if max_price: body_text += f"_(Budget: {currency}{max_price})_\n"
            body_text += "\n"
            
            for i, prod in enumerate(filtered[:max_items], 1):
                body_text += f"{i}. {prod['name']} - {currency}{prod['price']}\n"

            # Check if we should use Buttons or Text
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
                            "buttons": [
                                {"type": "reply", "reply": {"id": "select_1", "title": "Select #1"}},
                                {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}
                            ]
                        }
                    }
                }
                send_whatsapp_message(phone_number, payload)
            else:
                # Fallback to plain text if buttons are disabled
                send_whatsapp_message(phone_number, body_text)
            
            save_message_to_db(phone_number, "assistant", body_text, phone_number_id)
            return {"status": "catalog_sent"}

    # 6. CONVERSATIONAL AI (Answer questions like "M means?")
    system_prompt = client.get("system_prompt", "You are Stitch for Zyphor Apparel.")
    ai_reply = generate_replay(text, system_prompt, phone_number)
    send_whatsapp_message(phone_number, ai_reply)
    save_message_to_db(phone_number, "assistant", ai_reply, phone_number_id)
    
    return {"status": "conversational_complete"}