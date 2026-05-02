import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt, generate_replay  #
from app.modules.clothing.prompts import CLOTHING_SYSTEM_PROMPT

def find_manual_intent(user_message, client_data):
    """Checks for exact keyword matches with word boundaries."""
    keywords_config = client_data.get("keywords", {})
    user_message = user_message.lower().strip()
    for intent, keywords in keywords_config.items():
        for word in keywords:
            pattern = rf"\b{re.escape(word.lower())}\b"
            if re.search(pattern, user_message):
                return intent
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Log incoming message
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    # 2. Check for Manual Intent (Keyword Match)
    manual_intent = find_manual_intent(text, client)
    intent = None

    # 3. If no manual intent, use AI for structured extraction
    if not manual_intent:
        ai_query = f"{CLOTHING_SYSTEM_PROMPT}\n\nUser Message: {text}"
        ai_raw = run_custom_prompt(ai_query) #
        try:
            clean_json = ai_raw.replace('```json', '').replace('```', '').strip()
            ai_data = json.loads(clean_json)
            intent = ai_data.get("intent")
        except:
            intent = "UNKNOWN"
    else:
        intent = manual_intent

    # 4. DYNAMIC UI LOGIC: Generate catalog from DB products
    if intent in ["view_collection", "SHOW_PRODUCTS", "FILTER_PRICE"]:
        products = client.get("products", [])
        if not products:
            reply = "Our catalog is currently being updated."
            send_whatsapp_message(phone_number, reply)
            return {"status": "no_products"}

        product_list_text = f"👕 *{client.get('name', 'Zyphor Apparel')} Collection*\n\n"
        for i, prod in enumerate(products[:3], 1):
            product_list_text += f"{i}. {prod['name']} - ₹{prod['price']}\n"

        header_image = products[0].get("image_url", "https://i.postimg.cc/zD0bxRP7/shopping.webp")

        catalog_payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "image", "image": {"link": header_image}},
                "body": {"text": product_list_text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "select_1", "title": "Select #1"}},
                        {"type": "reply", "reply": {"id": "show_more", "title": "Show More"}},
                        {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}
                    ]
                }
            }
        }
        send_whatsapp_message(phone_number, catalog_payload)
        save_message_to_db(phone_number, "assistant", "Sent Dynamic Catalog UI", phone_number_id)
        return {"status": "ui_sent"}

    # 5. Handle simple text responses from DB (e.g. Size Guide)
    elif manual_intent and manual_intent in client.get("intent_responses", {}):
        reply = client["intent_responses"][manual_intent]
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        return {"status": "manual_text_sent"}

    # 6. CONVERSATIONAL FALLBACK: Handles "What is M?" or "M means?"
    else:
        # Use your system_prompt from the DB
        system_instructions = client.get("system_prompt", "You are Stitch, the fashion assistant for Zyphor Apparel.")
        
        # Use your conversational function that pulls history
        ai_conversational_reply = generate_replay(text, system_instructions, phone_number) #
        
        send_whatsapp_message(phone_number, ai_conversational_reply)
        save_message_to_db(phone_number, "assistant", ai_conversational_reply, phone_number_id)
        return {"status": "ai_conversation_sent"}