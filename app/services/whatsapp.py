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
    
    
def send_whatsapp_image(to: str, image_url: str, caption: str = ""):
    print("=== SENDING IMAGE ===")
    print("TO:", to)
    print("IMAGE:", image_url)
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    print("Meta status code:", response.status_code)
    print("Meta response:", response.text)
    
    
def send_whatsapp_buttons(to: str, text: str):
    print("=== SENDING BUTTON MESSAGE ===")
    print("TO:", to)
    print("TEXT:", text)

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "order",
                            "title": "Order Now"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "menu",
                            "title": "View Menu"
                        }
                    }
                ]
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    print("Meta status code:", response.status_code)
    print("Meta response:", response.text)