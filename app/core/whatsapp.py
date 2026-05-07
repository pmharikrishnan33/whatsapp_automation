import requests
from typing import Union, List, Dict
from app.core.config import WHATSAPP_TOKEN, PHONE_NUMBER_ID

def send_whatsapp_message(to: str, text: str, buttons: List[Dict] = None, image_url: str = None):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    if buttons:
        interactive_payload = {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": str(btn.get("id"))[:256],
                            "title": str(btn.get("title"))[:20]
                        }
                    } for btn in buttons[:3]
                ]
            }
        }
        
        # Add the image header if an image URL is provided!
        if image_url:
            interactive_payload["header"] = {
                "type": "image",
                "image": {"link": image_url}
            }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive_payload
        }
    elif image_url:
        # Standard image message without buttons
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": text}
        }
    else:
        # Standard Text Message
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            print("❌ Meta API Error:", response.text)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ SEND ERROR: {e}")
        return False