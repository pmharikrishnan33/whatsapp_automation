import re
from fastapi import APIRouter, Query, HTTPException
from app.config import VERIFY_TOKEN
from app.services.whatsapp import send_whatsapp_message
from app.services.ai import generate_replay
from app.services.client_mananger import get_client_config
from app.services.memory import (
    save_message_to_db, 
    save_order_to_db, 
    get_state, 
    set_state, 
    get_history, 
    add_to_history,
    manage_client_credit
)
from app.utils.formatter import format_whatsapp_reply

router = APIRouter()

@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="verification failed")

@router.post("/webhook")
async def receive_message(body: dict):
    try:
        # 1. Extract metadata
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")
        
        if not messages:
            return {"status": "no message"}

        message = messages[0]
        phone_number = message["from"]
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        text = message.get("text", {}).get("body", "")
        text_lower = text.lower().strip()

        # 2. Fetch client configuration
        client = get_client_config(phone_number_id)
        if not client:
            return {"status": "error", "message": "Client not found"}

        # --- 3. THE CREDIT LIMIT CUTOFF ---
        current_spend = client.get("current_month_spend", 0)
        credit_limit = client.get("monthly_credit_limit", 500) # Default to 500 if not set in DB

        if current_spend >= credit_limit:
            # Save the message so the business owner can see it, but DO NOT reply.
            save_message_to_db(phone_number, "user", text, phone_number_id)
            print(f"Credit limit exceeded for {phone_number_id}. Ignoring message to prevent Meta charges.")
            return {"status": "limit_exceeded_ignored"}
        # ----------------------------------

        # 4. SILENT CREDIT MANAGEMENT (Invisible to User)
        manage_client_credit(phone_number, phone_number_id)

        # 5. Save incoming message to DB
        save_message_to_db(phone_number, "user", text, phone_number_id)

        # 6. Handle State-Based Order Flow
        current_state = get_state(phone_number)
        client_keywords = client.get("keywords", {})

        # Trigger Order Flow via Regex Keyword Match
        order_triggers = client_keywords.get("order", [])
        is_order_trigger = any(re.search(r'\b' + re.escape(t.lower()) + r'\b', text_lower) for t in order_triggers)

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
            add_to_history(phone_number, "pending_items", text)
            reply = f"Confirming your order: {text}\n\nType 'Confirm', 'Edit', or 'Cancel'."
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

        # 7. Handle Standard Keyword Intents (Regex Partial Match Fix)
        detected_intent = None
        for intent, triggers in client_keywords.items():
            if intent != "order":
                if any(re.search(r'\b' + re.escape(t.lower()) + r'\b', text_lower) for t in triggers):
                    detected_intent = intent
                    break

        if detected_intent:
            raw_reply = client.get("intent_responses", {}).get(detected_intent)
            if raw_reply:
                formatted_reply = format_whatsapp_reply(raw_reply)
                send_whatsapp_message(phone_number, formatted_reply)
                save_message_to_db(phone_number, "assistant", formatted_reply, phone_number_id)
                return {"status": "intent_replied"}

        # 8. AI Fallback
        system_prompt = client.get("system_prompt", "You are a helpful assistant.")
        raw_ai_reply = generate_replay(text, system_prompt, phone_number)
        formatted_ai_reply = format_whatsapp_reply(raw_ai_reply)
        
        send_whatsapp_message(phone_number, formatted_ai_reply)
        save_message_to_db(phone_number, "assistant", formatted_ai_reply, phone_number_id)
        add_to_history(phone_number, "user", text)
        add_to_history(phone_number, "assistant", formatted_ai_reply)

        return {"status": "ai_replied"}

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        return {"error": str(e)}