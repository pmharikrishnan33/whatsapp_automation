import requests
from app.config import WHATSAPP_TOKEN, PHONE_NUMBER_ID

def send_whatsapp_message(to: str, message: str):

    print("=== SENDING WHATSAPP MESSAGE ===")
    print("TO:", to)
    print("MESSAGE:", message)

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": message
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    print("Meta status code:", response.status_code)
    print("Meta response:", response.text)
    
    
def send_whatsapp_list(phone_number, button_text, options):
    import requests

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    rows = [{"id": f"opt_{i}", "title": opt} for i, opt in enumerate(options)]

    data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "Please choose an option"},
            "action": {
                "button": button_text,
                "sections": [
                    {
                        "title": "Options",
                        "rows": rows
                    }
                ]
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, json=data)
    print("List response:", res.text)