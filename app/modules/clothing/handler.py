import re
import json
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import run_custom_prompt
from app.modules.clothing.prompt import CLOTHING_SYSTEM_PROMPT

def find_manual_intent(user_message, client_data):
    """
    Checks for exact keyword matches using word boundaries.
    Ensures 'hi' matches but 'hike' does not.
    """
    keywords_config = client_data.get("keywords", {})
    user_message = user_message.lower().strip()

    for intent, keywords in keywords_config.items():
        for word in keywords:
            # \b matches word boundaries only
            pattern = rf"\b{re.escape(word.lower())}\b"
            if re.search(pattern, user_message):
                return intent
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    """
    Hybrid Handler: Manual Keyword Check -> AI Intent Extraction -> State Machine.
    """
    # 1. Log User Message
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    # 2. STEP 1: MANUAL KEYWORD CHECK (Saves AI Cost)
    manual_intent = find_manual_intent(text, client)
    
    if manual_intent:
        responses = client.get("intent_responses", {})
        reply = responses.get(manual_intent)
        
        if reply:
            send_whatsapp_message(phone_number, reply)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "manual_match", "intent": manual_intent}

    # 3. STEP 2: AI FALLBACK (For complex queries like 'tshirt under 500')
    ai_query = f"{CLOTHING_SYSTEM_PROMPT}\n\nUser Message: {text}"
    ai_raw_response = run_custom_prompt(ai_query) #
    
    try:
        clean_json = ai_raw_response.replace('```json', '').replace('```', '').strip()
        ai_data = json.loads(clean_json)
    except:
        ai_data = {"intent": "UNKNOWN"}

    intent = ai_data.get("intent")
    shop_name = client.get("name", "Zyphor Apparel")

    # 4. STEP 3: STATE MACHINE LOGIC (Handles interactive flows)[cite: 1]
    
    # Intent: VIEW COLLECTION / FILTER PRICE
    if intent in ["SHOW_PRODUCTS", "FILTER_PRICE", "view_collection"]:
        max_p = ai_data.get("max_price")
        header_text = f"Top Picks Under ₹{max_p}" if max_p else "Zyphor Collection"
        
        product_payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "image", "image": {"link": "https://i.postimg.cc/zD0bxRP7/shopping.webp"}},
                "body": {"text": f"👕 *{header_text}*\n\n1. Premium T-Shirt - ₹599\n2. Slim Fit Chinos - ₹1500\n3. Denim Jeans - ₹1200"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "select_1", "title": "Select #1"}},
                        {"type": "reply", "reply": {"id": "show_more", "title": "Show More"}},
                        {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}
                    ]
                }
            }
        }
        send_whatsapp_message(phone_number, product_payload)
        save_message_to_db(phone_number, "assistant", "Sent interactive catalog", phone_number_id)

    # Intent: SELECTION & SIZE
    elif intent == "SELECT_PRODUCT" or "select_" in text.lower():
        reply = "Great choice! 👕 What size do you need? (S, M, L, XL)"
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)

    # Intent: QUANTITY
    elif text.upper() in ["S", "M", "L", "XL"]:
        reply = f"Size {text.upper()} confirmed. How many units do you want?"
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)

    # Intent: ORDER CONFIRMATION
    elif text.isdigit() and int(text) < 10:
        reply = f"✅ Confirm order for {text} items?\nReply 'YES' to finalize."
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)

    # Final Fallback: AI Conversational Chat[cite: 1]
    else:
        fallback = "I didn't quite get that. Try 'show collection' or 'shirts under 1000'!"
        send_whatsapp_message(phone_number, fallback)
        save_message_to_db(phone_number, "assistant", fallback, phone_number_id)

    return {"status": "success", "intent": intent}