from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import generate_replay

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Clean incoming text
    user_message = text.lower().strip()
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    # 2. Extract configuration from the database client object
    shop_name = client.get("name", "Zyphor Apparel")
    keywords = client.get("keywords", {})
    intent_responses = client.get("intent_responses", {})
    interactive_config = client.get("interactive_config", {})
    
    # 3. Determine the user's intent by matching words in the message
    matched_intent = None
    for intent, words in keywords.items():
        if any(word in user_message for word in words):
            matched_intent = intent
            break

    # 4. Handle 'view_collection' specifically for the Interactive T-Shirt menu
    if matched_intent == "view_collection":
        
        menu_enabled = interactive_config.get("enabled", False)
        
        if menu_enabled:
            print(f"Triggering DB interactive menu for {phone_number}")
            
            # Fetch dynamic details from DB, use fallbacks if missing
            img_url = interactive_config.get("image_url", "https://i.postimg.cc/0Nz11h8Q/men-s-t-shirt-realistic-mockup-in-different-colors-ai-generated-photo.jpg")
            body_text = interactive_config.get("body_text", f"*{shop_name} Collection*\nPremium Quality | Unisex\n₹599.00")
            
            interactive_menu = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "header": {
                        "type": "image",
                        "image": {"link": img_url}
                    },
                    "body": {"text": body_text},
                    "action": {
                        "buttons": [] # We will populate this from the DB
                    }
                }
            }
            
            # Dynamically build buttons from DB (WhatsApp allows max 3)
            db_buttons = interactive_config.get("buttons", [])
            for btn in db_buttons[:3]: 
                interactive_menu["interactive"]["action"]["buttons"].append({
                    "type": "reply",
                    "reply": {"id": btn.get("id"), "title": btn.get("title")}
                })
                
            send_whatsapp_message(to=phone_number, message=interactive_menu)
            save_message_to_db(phone_number, "assistant", "Sent DB interactive T-shirt menu", phone_number_id)
            return {"status": "success", "action": "sent_interactive_menu"}
            
        else:
            # If flag is false, send standard text response instead
            reply_text = intent_responses.get("view_collection", "Here is our collection...")
            send_whatsapp_message(to=phone_number, message=reply_text)
            save_message_to_db(phone_number, "assistant", reply_text, phone_number_id)
            return {"status": "success", "action": "sent_collection_text"}

    # 5. Handle all other matched intents (greeting, size_guide, location, order)
    elif matched_intent:
        reply_text = intent_responses.get(matched_intent, "I'm here to help!")
        send_whatsapp_message(to=phone_number, message=reply_text)
        save_message_to_db(phone_number, "assistant", reply_text, phone_number_id)
        return {"status": "success", "action": f"sent_{matched_intent}"}

    # 6. Fallback if no keywords matched
    else:
        print(f"No keywords matched. Routing {phone_number} to AI Fallback.")
        
        # Extract the AI persona from the DB, with a safe default just in case
        system_prompt = client.get(
            "system_prompt", 
            f"You are a helpful fashion assistant for {shop_name}. Keep replies concise and stylish."
        )
        
        # Call your AI service to generate a response. 
        # (Assuming your AI function is asynchronous)
        try:
            ai_reply = await generate_replay(system_prompt=system_prompt, user_message=user_message)
        except Exception as e:
            print(f"AI Generation Error: {e}")
            ai_reply = f"I'm having a little trouble thinking right now, but you can always ask to see our collection!"
        
        # Send the AI's custom response back to the user
        send_whatsapp_message(to=phone_number, message=ai_reply)
        save_message_to_db(phone_number, "assistant", ai_reply, phone_number_id)
        
        return {"status": "success", "action": "sent_ai_fallback"}