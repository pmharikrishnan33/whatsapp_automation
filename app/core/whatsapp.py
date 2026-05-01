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

    # 1. Handle Standard Text (String)
    if isinstance(message, str):
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {
                "body": message
            }
        }
        
    # 2. Handle Interactive/Complex Messages (Dictionary)
    elif isinstance(message, dict):
        payload = message
        # Failsafe: Ensure the 'to' number is injected if you forgot it in the dict
        if "to" not in payload:
            payload["to"] = to
            
    else:
        print("❌ Error: Message must be a string or dictionary")
        return None

    # Send the request to Meta
    response = requests.post(url, headers=headers, json=payload)
    
    print("Meta status code:", response.status_code)
    if response.status_code != 200:
        print("Meta Error response:", response.text)
        
    return response.json() if response.status_code == 200 else None