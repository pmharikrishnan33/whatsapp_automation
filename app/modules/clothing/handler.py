from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Save the incoming user message to the database
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    shop_name = client.get("name", "Zyphor Technologies")
    text_lower = text.lower()
    
    # 2. Trigger the interactive T-shirt message
    if "t-shirts" in text_lower or "hi" in text_lower:
        
        interactive_payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "image",
                    "image": {
                        "link": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&q=80&w=800"
                    }
                },
                "body": {
                    "text": f"*{shop_name} Premium T-Shirt*\n100% Cotton | Premium Quality | Unisex\n₹599.00"
                },
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "details_01", "title": "View Details"}},
                        {"type": "reply", "reply": {"id": "size_01", "title": "Choose Size"}},
                        {"type": "reply", "reply": {"id": "cart_01", "title": "Add to Cart"}}
                    ]
                }
            }
        }
        
        # Send the interactive message payload
        send_whatsapp_message(phone_number, interactive_payload)
        
        # Save the bot's action to memory
        save_message_to_db(phone_number, "assistant", "Sent Premium T-Shirt interactive message", phone_number_id)
        
        return {"status": "clothing_interactive_sent"}
        
    # 3. Fallback logic if they say something else
    else:
        reply = f"👔 Welcome to {shop_name}! Try saying 'show me t-shirts' to see our latest collection."
        
        # Note: Ensure your send_whatsapp_message can handle both dicts (above) and strings (below), 
        # or format this reply into a standard text payload dictionary.
        send_whatsapp_message(phone_number, reply)
        save_message_to_db(phone_number, "assistant", reply, phone_number_id)
        
        return {"status": "clothing_fallback_sent"}