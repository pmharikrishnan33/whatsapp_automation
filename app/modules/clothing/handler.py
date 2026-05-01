from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Clean the incoming text (make it lowercase and remove extra spaces)
    user_message = text.lower().strip()
    
    # Save user message to your DB
    save_message_to_db(phone_number, "user", text, phone_number_id)

    # 2. Check if the message is "hi"
    if user_message == "hi" or user_message == "show me t-shirts":
        
        print(f"Triggering interactive T-shirt menu for {phone_number}")
        
        # 3. Build the exact payload from your screenshot
        interactive_menu = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "image",
                    "image": {
                        # You must replace this with a publicly accessible URL of your image
                        "link": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&q=80&w=800" 
                    }
                },
                "body": {
                    "text": "*Zyphor Premium T-Shirt*\n100% Cotton | Premium Quality | Unisex\n₹599.00"
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
        fallback_text = "Hello! Send 'Hi' to see our latest T-shirt collection."
        send_whatsapp_message(to=phone_number, message=fallback_text)
        save_message_to_db(phone_number, "assistant", fallback_text, phone_number_id)
        
        return {"status": "success", "action": "sent_fallback"}