from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Clean the incoming text
    user_message = text.lower().strip()
    
    # Save user message to your DB
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    shop_name = client.get("name", "Zyphor Technologies")

    # 2. Check if the message triggers the T-shirt menu
    if user_message == "hi" or user_message == "show me t-shirts":
        
        print(f"Triggering interactive T-shirt menu for {phone_number}")
        
        # 3. Build the payload using a DIRECT image link
        interactive_menu = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "image",
                    "image": {
                        # Ensure this is your public, direct image link ending in .jpg or .png
                        "link": "https://raw.githubusercontent.com/zyphor/assets/main/zyphor-black-tshirt.jpg" 
                    }
                },
                "body": {
                    "text": f"*{shop_name} Premium T-Shirt*\n100% Cotton | Premium Quality | Unisex\n₹599.00"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": "view_details", "title": "View Details"}
                        },
                        {
                            "type": "reply",
                            "reply": {"id": "choose_size", "title": "Choose Size"}
                        },
                        {
                            "type": "reply",
                            "reply": {"id": "add_to_cart", "title": "Add to Cart"}
                        }
                    ]
                }
            }
        }
        
        # 4. Send the dictionary using your updated helper function
        send_whatsapp_message(to=phone_number, message=interactive_menu)
        
        # Save bot action to DB
        save_message_to_db(phone_number, "assistant", "Sent interactive T-shirt menu", phone_number_id)
        
        return {"status": "success", "action": "sent_interactive_menu"}

    # --- Fallback for any other message ---
    else:
        fallback_text = f"👔 Welcome to {shop_name}! Try saying 'show me t-shirts' to see our latest collection."
        
        send_whatsapp_message(to=phone_number, message=fallback_text)
        save_message_to_db(phone_number, "assistant", fallback_text, phone_number_id)
        
        return {"status": "success", "action": "sent_fallback"}