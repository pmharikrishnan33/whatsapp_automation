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
async def receive_message(body:dict):
    print(json.dumps(body,indent=2))
    print("full incoming data")
    print(body)

    try:
        entry=body["entry"][0]
        changes=entry["changes"][0]
        value=changes["value"]

        messages=value.get("messages")

        if messages:
            message=messages[0]
            phone_number=message["from"]
            text=message["text"]["body"]

            print("user:",phone_number)
            print("message:",text)
            
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            print("Business ID:", phone_number_id)

            client = get_client_config(phone_number_id)
            print("Client config:", client)
            
            if not client:
                print("Client not found — using default")
                system_prompt = "You are a helpful assistant."
            else:
                system_prompt = client["system_prompt"]
            raw_reply = generate_replay(text, system_prompt, phone_number)
            reply = format_whatsapp_reply(raw_reply)
            add_to_history(phone_number, "user", text)
            add_to_history(phone_number, "assistant", reply)    

            send_whatsapp_message(phone_number, reply)
            print("Message sent to WhatsApp")

            return{
                "from":phone_number,
                "message":text,
                "reply":reply
            }
        return{"status":"no message found"}
    except Exception as e:
        print("REAL ERROR:", str(e))
        return {"error": str(e)}
    
@router.get("/test-send")
def test_send():
    send_whatsapp_message("919495470356", "Direct test message")
    return {"status": "sent"}
    