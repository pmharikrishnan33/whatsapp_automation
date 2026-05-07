import re
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import generate_replay

def detect_signal(text, keyword_list):
    """Helper to match keywords using regex word boundaries."""
    for word in keyword_list:
        if re.search(rf"\b{re.escape(word.lower())}\b", text.lower()):
            return True
    return False

def extract_price_filter(text):
    """Detects price signals like 'under 1000' or 'below 500'."""
    patterns = [r'(?:under|below|less than|<=?)\s*(\d+)', r'(\d+)\s*(?:below|under)']
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return int(match.group(1))
    return None

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # 1. Initialize variables from JSON config
    user_msg = text.lower().strip()
    ui = client.get("ui", {})
    currency = ui.get("currency", "₹")
    max_items = ui.get("max_items_per_message", 3)
    features = client.get("features", {})
    
    keywords = client.get("keywords", {})
    categories_map = keywords.get("categories", {})
    
    # 2. Extract User Intent
    is_greeting = detect_signal(user_msg, keywords.get("greeting", []))
    is_collection_req = detect_signal(user_msg, keywords.get("view_collection", []))
    max_price = extract_price_filter(user_msg)
    
    # Detect specific category
    detected_cat = None
    for cat_name, synonyms in categories_map.items():
        if detect_signal(user_msg, synonyms):
            detected_cat = cat_name
            break

    # 3. Decision Tree Logic
    
    # CASE A: Greeting (Only if no specific product/category mentioned)
    if is_greeting and not (detected_cat or is_collection_req):
        reply = client.get("intent_responses", {}).get("greeting", "Hello! How can I help you today?")
        return await finalize_response(phone_number, reply, phone_number_id, "greeting")

    # CASE B: View All Collection / List Categories
    if is_collection_req and not detected_cat:
        avail_cats = ", ".join([c.capitalize() for c in categories_map.keys()])
        reply = f"🛍️ *Our Collections*\n\nWe have a wide range of:\n* {avail_cats.replace(', ', '\n* ')}\n\n_Type a category name (e.g., 'Show shirts') to see products!_"
        return await finalize_response(phone_number, reply, phone_number_id, "collection_list")

    # CASE C: Product Filtering (Category and/or Price)
    if detected_cat or max_price:
        products = client.get("products", [])
        
        # Filter logic
        filtered = [
            p for p in products 
            if (not detected_cat or p["category"] == detected_cat) 
            and (not max_price or p["price"] <= max_price)
        ]

        if filtered:
            header = f"👕 *{client.get('name')} - {detected_cat.capitalize() if detected_cat else 'Deals'}*\n"
            if max_price:
                header += f"_(Budget: {currency}{max_price})_\n"
            header += "__________________________\n\n"
            
            body = header
            # Respect max_items_per_message from JSON
            for i, p in enumerate(filtered[:max_items], 1):
                body += f"*{i}. {p['name']}*\n"
                body += f"💰 {currency}{p['price']}\n"
                body += f"📝 {p.get('description', '')}\n\n"
            
            if len(filtered) > max_items:
                body += f"_+ {len(filtered) - max_items} more items available!_"

            return await finalize_response(phone_number, body, phone_number_id, "catalog_sent")
        else:
            # Fallback for no matches
            reply = f"Sorry, we don't have items matching that criteria right now. Check out our other categories!"
            return await finalize_response(phone_number, reply, phone_number_id, "no_match")

    # CASE D: AI Fallback
    if features.get("ai_fallback"):
        ai_reply = generate_replay(text, client.get("system_prompt"), phone_number)
        return await finalize_response(phone_number, ai_reply, phone_number_id, "ai_reply")

    return {"status": "no_action"}

async def finalize_response(phone_number, text, phone_id, status):
    """Helper to send, save, and log the response."""
    result = send_whatsapp_message(phone_number, text)
    print(f"[{status.upper()}] Result:", result)
    save_message_to_db(phone_number, "assistant", text, phone_id)
    return {"status": status}