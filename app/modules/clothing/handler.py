import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def extract_price_signal(text: str):
    """
    Regex to capture price signals (e.g., 'under 500') without AI cost.
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
    Uses Word Boundaries (\b) to ensure 'hi' doesn't trigger inside 'shirt'.
    Maps synonyms to internal categories.
    """
    categories_map = client_data.get("keywords", {}).get("categories", {})
    user_msg_low = user_msg.lower().strip()
    
    for category_name, synonyms in categories_map.items():
        for word in synonyms:
            # \b ensures 'hi' matches but 'shirt' does not
            if re.search(rf"\b{re.escape(word.lower())}\b", user_msg_low):
                return category_name
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Log incoming message
    save_message_to_db(phone_number, "user", text, phone_number_id)
    user_msg_low = text.lower().strip()
    
    # 2. Configuration & Signals
    features = client.get("features", {})
    ui_config = client.get("ui", {})
    keywords = client.get("keywords", {})
    
    detected_category = detect_category_signal(user_msg_low, client)
    max_price = extract_price_signal(user_msg_low)
    
    # Identify if it's a general collection or greeting request
    is_collection_req = any(re.search(rf"\b{re.escape(w.lower())}\b", user_msg_low) 
                           for w in keywords.get("view_collection", []))
    is_greeting = any(re.search(rf"\b{re.escape(w.lower())}\b", user_msg_low) 
                      for w in keywords.get("greeting", []))

    # 3. ROUTING LOGIC

    # CASE A: Pure Greeting only (No product/category signals)
    if is_greeting and not (detected_category or max_price or is_collection_req):
        reply = client.get("intent_responses", {}).get("greeting")
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        return {"status": "greeting_sent"}

    # CASE B: AI Extraction (Only if manual signals are missing)
    if features.get("ai_fallback") and not (detected_category or max_price or is_collection_req):
        # AI check for complex phrases like 'something budget friendly'
        if len(user_msg_low) > 10:
            ai_query = f"{CLOTHING_SYSTEM_PROMPT}\n\nUser Message: {text}"
            ai_raw = run_custom_prompt(ai_query)
            try:
                ai_data = json.loads(ai_raw.replace('```json', '').replace('```', '').strip())
                max_price = max_price or ai_data.get("max_price")
                detected_category = detected_category or ai_data.get("category")
                if ai_data.get("intent") in ["SHOW_PRODUCTS", "FILTER_PRICE"]:
                    is_collection_req = True
            except:
                pass

    # CASE C: Filtered Catalog Display
    if detected_category or max_price or is_collection_req:
        all_products = client.get("products", [])
        
        # Combine category and price filters
        filtered = [
            p for p in all_products 
            if (not max_price or p['price'] <= max_price) and 
               (not detected_category or p.get('category') == detected_category)
        ]

        if filtered:
            currency = ui_config.get("currency", "₹")
            max_items = ui_config.get("max_items_per_message", 3)
            
            # Formatting the UI with Image, Title, Price, and Description
            body_text = f"👕 *{client.get('name')} {detected_category.title() if detected_category else ''} Selection*\n"
            if max_price: body_text += f"_(Budget: {currency}{max_price})_\n"
            body_text += "__________________________\n\n"
            
            for i, prod in enumerate(filtered[:max_items], 1):
                body_text += f"*{i}. {prod['name']}*\n"
                body_text += f"💰 Price: {currency}{prod['price']}\n"
                body_text += f"📝 {prod.get('description', 'Premium quality')}\n\n"

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
                send_whatsapp_message(phone_number, body_text)
            return {"status": "catalog_sent"}
        
        else:
            # Case: Not Available / Suggest categories
            avail_cats = ", ".join(keywords.get("categories", {}).keys())
            reply = f"Sorry, we don't have that in stock. Our available categories are: *{avail_cats}*."
            send_whatsapp_message(phone_number, reply)
            return {"status": "not_available"}

    # CASE D: Conversational Fallback (Uses history for "What is M?")
    system_prompt = client.get("system_prompt", "You are Stitch, the fashion assistant.")
    ai_reply = generate_replay(text, system_prompt, phone_number)
    send_whatsapp_message(phone_number, ai_reply)
    save_message_to_db(phone_number, "assistant", ai_reply, phone_number_id)
    return {"status": "ai_reply_sent"}