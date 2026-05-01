import re
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import generate_replay

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Clean incoming text & Save to DB[cite: 1]
    user_message = text.lower().strip()
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    # 2. Extract DB Configurations[cite: 1]
    shop_name = client.get("name", "Zyphor Apparel")
    keywords = client.get("keywords", {})
    intent_responses = client.get("intent_responses", {})
    
    # 3. Determine the user's intent by matching words in the message[cite: 1]
    matched_intent = None
    for intent, words in keywords.items():
        if any(word in user_message for word in words):
            matched_intent = intent
            break

    # ---------------------------------------------------------
    # 4. INTENT: VIEW COLLECTION (With Category & Price Filters)
    # ---------------------------------------------------------
    if matched_intent == "view_collection":
        print(f"Triggering collection menu for {phone_number}")
        
        all_products = client.get("products", [])
        filtered_products = all_products
        
        # --- A. Category Filtering ---
        target_category = None
        if any(word in user_message for word in ["shirt", "tshirt", "tee", "t-shirt"]):
            target_category = "shirt"
        elif any(word in user_message for word in ["pant", "jeans", "chinos", "trousers"]):
            target_category = "pant"
            
        if target_category:
            filtered_products = [p for p in filtered_products if p.get("category") == target_category]

        # --- B. Price Filtering (Regex) ---
        price_limit = None
        if "under" in user_message or "below" in user_message:
            numbers = re.findall(r'\d+', user_message)
            if numbers:
                price_limit = int(numbers[0])
                
        if price_limit:
            filtered_products = [p for p in filtered_products if p.get("price", 0) <= price_limit]

        # --- C. Generate the Reply ---
        if not filtered_products:
            reply = "Sorry, we don't have exactly what you're looking for right now. Try adjusting your search!"
            send_whatsapp_message(to=phone_number, message=reply)
            save_message_to_db(phone_number, "assistant", reply, phone_number_id)
            return {"status": "no_products_found"}

        item_type = target_category + "s" if target_category else "items"
        intro_text = f"Here are our best {item_type} under ₹{price_limit}:" if price_limit else f"Here is our latest collection of {item_type}:"

        send_whatsapp_message(to=phone_number, message=intro_text)

        # --- D. Send Interactive Messages (Max 3 to prevent spam triggers) ---
        for product in filtered_products[:3]:
            interactive_menu = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "header": {
                        "type": "image",
                        "image": {"link": product["image_url"]}
                    },
                    "body": {
                        "text": f"*{product['name']}*\nPremium Quality | Unisex\n₹{product['price']}.00"
                    },
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": f"details_{product['id']}", "title": "View Details"}},
                            {"type": "reply", "reply": {"id": f"size_{product['id']}", "title": "Choose Size"}},
                            {"type": "reply", "reply": {"id": f"cart_{product['id']}", "title": "Add to Cart"}}
                        ]
                    }
                }
            }
            send_whatsapp_message(to=phone_number, message=interactive_menu)
            
        save_message_to_db(phone_number, "assistant", f"Sent {len(filtered_products[:3])} products", phone_number_id)
        return {"status": "success", "action": "sent_filtered_collection"}

    # ---------------------------------------------------------
    # 5. INTENT: STANDARD KEYWORDS (Greetings, Size, Location)
    # ---------------------------------------------------------
    elif matched_intent:
        reply_text = intent_responses.get(matched_intent, "I'm here to help!")
        send_whatsapp_message(to=phone_number, message=reply_text)
        save_message_to_db(phone_number, "assistant", reply_text, phone_number_id)
        return {"status": "success", "action": f"sent_{matched_intent}"}

    # ---------------------------------------------------------
    # 6. NO INTENT MATCHED: AI CHAT FALLBACK
    # ---------------------------------------------------------
    else:
        print(f"No keywords matched. Routing {phone_number} to AI Fallback.")
        system_prompt = client.get("system_prompt", f"You are a fashion assistant for {shop_name}. Keep replies concise and stylish.")
        
        try:
            ai_reply = generate_replay(system_prompt=system_prompt, user_message=user_message, phone_number=phone_number)
        except Exception as e:
            print(f"AI Chat Error: {e}")
            ai_reply = "I'm having a little trouble thinking right now, but you can always ask to see our collection!"
        
        send_whatsapp_message(to=phone_number, message=ai_reply)
        save_message_to_db(phone_number, "assistant", ai_reply, phone_number_id)
        return {"status": "success", "action": "sent_ai_fallback"}