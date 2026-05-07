from fastapi import FastAPI, Request, Query, HTTPException
from app.core.config import VERIFY_TOKEN
from app.core.client_manager import get_client_config
from app.modules.clothing.handler import handle_clothing_logic

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "ignored"}

        msg = messages[0]
        from_phone = msg["from"]
        phone_id = value["metadata"]["phone_number_id"]
        
        # MANUAL CHECK: Is it a button click or typed text?
        if msg.get("type") == "interactive":
            # Extract the ID we hid in the button
            text_data = msg["interactive"]["button_reply"]["id"]
        else:
            text_data = msg.get("text", {}).get("body", "")

        # Fetch the specific client configuration from DB
        client = get_client_config(phone_id)
        if not client:
            return {"status": "client_not_found"}

        # Route to Clothing Logic
        await handle_clothing_logic(client, from_phone, text_data, phone_id)
        
        return {"status": "success"}
    except Exception as e:
        print(f"🚨 WEBHOOK ERROR: {e}")
        return {"status": "error"}

@app.get("/webhook")
def verify(hub_mode: str = Query(None, alias="hub.mode"), 
           hub_token: str = Query(None, alias="hub.verify_token"), 
           hub_challenge: str = Query(None, alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403)