from app.core.whatsapp import send_whatsapp_message
from app.core.memory import (
    save_message_to_db, save_order_to_db, get_state, 
    set_state, get_history, add_to_history, manage_client_credit
)
from app.services.ai import generate_replay, generate_receipt # Using your old AI functions
from app.core.formatter import format_whatsapp_reply

async def handle_restaurant_logic(client, phone_number, text, phone_number_id):
    text_lower = text.lower().strip()

    # --- 1. THE CREDIT LIMIT CUTOFF (From your old code) ---
    current_spend = client.get("current_month_spend", 0)
    credit_limit = client.get("monthly_credit_limit", 500)

    if current_spend >= credit_limit:
        save_message_to_db(phone_number, "user", text, phone_number_id)
        print(f"Credit limit exceeded for {phone_number_id}. Ignoring message.")
        return {"status": "limit_exceeded_ignored"}

    # 2. SILENT CREDIT MANAGEMENT & LOGGING
    manage_client_credit(phone_number, phone_number_id)
    save_message_to_db(phone_number, "user", text, phone_number_id)

    # 3. STATE ENGINE (Identical logic to your old webhook)
    current_state = get_state(phone_number)
    client_keywords = client.get("keywords", {})
    order_triggers = client_keywords.get("order", [])
    is_order_trigger = any(t.lower() in text_lower for t in order_triggers)

    # Trigger Order Flow
    if is_order_trigger:
        if not client.get("order_enabled", False):
            reply = client.get("intent_responses", {}).get("order_disabled_msg", "Ordering is unavailable.")
            send_whatsapp_message(phone_number, reply)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "order_disabled"}
        
        menu = client.get("intent_responses", {}).get("view_menu", "Please select items.")
        reply = f"{menu}\n\nPlease reply with the items and quantity you need."
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        set_state(phone_number, "AWAITING_ITEMS")
        return {"status": "order_started"}

    # Process ongoing Order states
    if current_state == "AWAITING_ITEMS":
        menu_text = client.get("intent_responses", {}).get("view_menu", "")
        clean_receipt = generate_receipt(text, menu_text) # Calls your old AI service
        add_to_history(phone_number, "pending_items", clean_receipt)
        
        reply = f"Please check your order:\n\n{clean_receipt}\n\nType 'Confirm', 'Edit', or 'Cancel'."
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        set_state(phone_number, "AWAITING_CONFIRMATION")
        return {"status": "items_pending"}

    elif current_state == "AWAITING_CONFIRMATION":
        if "confirm" in text_lower:
            reply = "Please send your Name, Location, and Phone Number."
            set_state(phone_number, "AWAITING_DETAILS")
        elif "edit" in text_lower:
            menu = client.get("intent_responses", {}).get("view_menu", "")
            reply = f"Let's try again.\n{menu}\n\nWhat items would you like?"
            set_state(phone_number, "AWAITING_ITEMS")
        elif "cancel" in text_lower:
            reply = "Order canceled."
            set_state(phone_number, "IDLE")
        else:
            reply = "Please type 'Confirm', 'Edit', or 'Cancel'."
        
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        return {"status": "confirm_step"}

    elif current_state == "AWAITING_DETAILS":
        pending_items = next((msg['content'] for msg in reversed(get_history(phone_number)) 
                                if msg['role'] == "pending_items"), "Unknown Items")
        save_order_to_db(phone_number, pending_items, {"details": text}, phone_number_id)
        
        reply = "Thank you! We will call you in 5 minutes."
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        set_state(phone_number, "IDLE")
        return {"status": "order_finalized"}

    # 4. Handle Standard Keyword Intents
    detected_intent = None
    for intent, triggers in client_keywords.items():
        if intent != "order" and any(t.lower() in text_lower for t in triggers):
            detected_intent = intent
            break

    if detected_intent:
        raw_reply = client.get("intent_responses", {}).get(detected_intent)
        if raw_reply:
            formatted_reply = format_whatsapp_reply(raw_reply)
            send_whatsapp_message(phone_number, formatted_reply)
            save_message_to_db(phone_number, "assistant", formatted_reply, phone_number_id)
            return {"status": "intent_replied"}

    # 5. AI Fallback (Using your generate_replay)
    system_prompt = client.get("system_prompt", "You are a helpful assistant.")
    raw_ai_reply = generate_replay(text, system_prompt, phone_number)
    formatted_ai_reply = format_whatsapp_reply(raw_ai_reply)
    
    send_whatsapp_message(phone_number, formatted_ai_reply)
    save_message_to_db(phone_number, "assistant", formatted_ai_reply, phone_number_id)
    add_to_history(phone_number, "user", text)
    add_to_history(phone_number, "assistant", formatted_ai_reply)

    return {"status": "ai_replied"}