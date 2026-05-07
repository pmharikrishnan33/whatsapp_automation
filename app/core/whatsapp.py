import requests
from typing import Union, List, Dict
from app.core.config import WHATSAPP_TOKEN, PHONE_NUMBER_ID

def send_whatsapp_message(to: str, text: str, buttons: List[Dict] = None):
    """
    Sends a WhatsApp message. If buttons are provided, it sends an Interactive Button message.
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    if buttons:
        # Meta allows a maximum of 3 reply buttons
        formatted_buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": str(btn.get("id"))[:256],
                    "title": str(btn.get("title"))[:20]
                }
            } for btn in buttons[:3]
        ]
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {"buttons": formatted_buttons}
            }
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ SEND ERROR: {e}")
        return False