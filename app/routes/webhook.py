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
        if not messages:
            return {"status": "no message"}

        message = messages[0]
        phone_number = message["from"]

        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        client = get_client_config(phone_number_id)

        text = ""
        is_button = False

        # -------------------------
        # 1. Detect button click
        # -------------------------
        if message.get("type") == "interactive":
            interactive = message["interactive"]

            if interactive.get("type") == "list_reply":
                text = interactive["list_reply"]["title"]
                is_button = True
        else:
            text = message["text"]["body"]

        text_lower = text.lower()

        # -------------------------
        # 2. Feature flag check
        # -------------------------
        features = client.get("features", {}) if client else {}
        button_enabled = features.get("buttons", False)

        # -------------------------
        # 3. Show buttons on trigger
        # -------------------------
        if button_enabled and not is_button:
            config = client.get("button_config", {})
            triggers = config.get("trigger", ["hi", "hello"])

            if text_lower in triggers:
                options = config.get("options", [])

                if options:
                    send_whatsapp_list(
                        phone_number,
                        config.get("button_text", "Choose"),
                        options
                    )
                    return {"status": "buttons sent"}

        # -------------------------
        # 4. AI handles everything else
        # (including button clicks)
        # -------------------------
        if not client:
            system_prompt = "You are a helpful assistant."
        else:
            system_prompt = client["system_prompt"]

        reply = generate_replay(text, system_prompt, phone_number)

        add_to_history(phone_number, "user", text)
        add_to_history(phone_number, "assistant", reply)

        send_whatsapp_message(phone_number, reply)

        return {
            "from": phone_number,
            "message": text,
            "reply": reply
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {"error": str(e)}
    
@router.get("/test-send")
def test_send():
    send_whatsapp_message("919495470356", "Direct test message")
    return {"status": "sent"}
    