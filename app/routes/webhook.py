from fastapi import APIRouter,Query,HTTPException,Request
from app.config import VERIFY_TOKEN
from app.services.whatsapp import send_whatsapp_message
from app.services.ai import generate_replay
import json
from app.services.client_mananger import get_client_config
from app.services.memory import add_to_history
from app.utils.formatter import format_whatsapp_reply


router =APIRouter()

@router.get("/webhook")
def verify_webhook(
    hub_mode:str=Query(None,alias="hub.mode"),
    hub_verify_token:str=Query(None,alias="hub.verify_token"),
    hub_challenge:str=Query(None,alias="hub.challenge")
):
    if hub_mode=="subscribe" and hub_verify_token==VERIFY_TOKEN:
        return int(hub_challenge)
    
    raise HTTPException(status_code=403,detail="verification failed")


@router.post("/webhook")
async def receive_message(body: dict):
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            message = messages[0]
            phone_number = message["from"]
            
            if "text" in message:
                text = message["text"]["body"]
            elif "interactive" in message:
                text = message["interactive"]["button_reply"]["title"]
            else:
                return {"status": "unsupported message type"}

            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            client = get_client_config(phone_number_id)
            
            if not client:
                system_prompt = "You are a helpful assistant."
                welcome_buttons = None
            else:
                system_prompt = client.get("system_prompt")
                welcome_buttons = client.get("welcome_buttons")

            is_greeting = text.lower().strip() in ["hi", "hello", "hey", "start"]

            if is_greeting and welcome_buttons:
                reply = f"Welcome to {client.get('name', 'our service')}! How can we help you today?"
                send_whatsapp_message(phone_number, reply, buttons=welcome_buttons)
                add_to_history(phone_number, "assistant", reply)
                return {"status": "welcome_buttons_sent"}

            reply = generate_replay(text, system_prompt, phone_number)
            add_to_history(phone_number, "user", text)
            add_to_history(phone_number, "assistant", reply)    

            send_whatsapp_message(phone_number, reply)

            return {
                "from": phone_number,
                "message": text,
                "reply": reply
            }
            
        return {"status": "no message found"}
    except Exception as e:
        print("REAL ERROR:", str(e))
        return {"error": str(e)}