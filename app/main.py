from fastapi import FastAPI, Request, Query, HTTPException
from app.core.config import VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID
from app.core.client_manager import get_client_config
from app.modules.restaurant.handler import handle_restaurant_logic
from app.modules.clothing.handler import handle_clothing_logic

app = FastAPI()

@app.post("/webhook")
async def receive_message(body: dict):
    try:
        # 1. Extraction (Infrastructure remains here)
        value = body["entry"][0]["changes"][0]["value"]
        messages = value.get("messages")
        if not messages: return {"status": "no message"}

        message = messages[0]
        customer_phone = message["from"]
        phone_id = value.get("metadata", {}).get("phone_number_id")
        text = message.get("text", {}).get("body", "")

        # 2. Fetch Client Config (Infrastructure remains here)
        client = get_client_config(phone_id)
        if not client: return {"status": "error"}

        # 3. ROUTE BASED ON INDUSTRY
        industry = client.get("industry", "restaurant") # Default to restaurant

        # app/main.py inside the webhook function
        try:
            if industry == "restaurant":
                await handle_restaurant_logic(client, customer_phone, text, phone_id)
            elif industry == "clothing":
                await handle_clothing_logic(client, customer_phone, text, phone_id)
        except Exception as e:
            print(f"CRASH DETECTED: {str(e)}") # This will show up in your Render logs

        return {"status": "success"}

    except Exception as e:
        print(f"WEBHOOK ERROR: {e}")
        return {"error": str(e)}

@app.get("/webhook")
def verify_webhook(hub_mode: str = Query(None, alias="hub.mode"), hub_verify_token: str = Query(None, alias="hub.verify_token"), hub_challenge: str = Query(None, alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403)