import requests
from typing import Union
from app.core.config import WHATSAPP_TOKEN, PHONE_NUMBER_ID

def send_whatsapp_message(to: str, message: Union[str, dict]):
    print("=== SENDING WHATSAPP MESSAGE ===")
    print("TO:", to)
    print("MESSAGE TYPE:", type(message))

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    if isinstance(message, str):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }

    elif isinstance(message, dict):
        payload = dict(message)
        payload.setdefault("messaging_product", "whatsapp")
        payload.setdefault("recipient_type", "individual")
        payload.setdefault("to", to)

    else:
        print("❌ Error: Message must be a string or dictionary")
        return {"ok": False, "error": "Invalid message type"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        print("Meta status code:", response.status_code)
        print("Meta response:", response.text)

        if response.status_code != 200:
            return {
                "ok": False,
                "status_code": response.status_code,
                "response": response.text
            }

        return {
            "ok": True,
            "response": response.json()
        }

    except Exception as e:
        print("WHATSAPP SEND ERROR:", str(e))
        return {"ok": False, "error": str(e)}