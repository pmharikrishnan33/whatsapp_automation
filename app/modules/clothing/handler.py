import re
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import generate_replay

# ==========================================
# 1. MANUAL RULE CHECKS (Bypass AI)
# ==========================================

def get_manual_category(text, categories_map):
    """Checks for exact word matches using regex boundaries."""
    for cat_name, synonyms in categories_map.items():
        for word in synonyms:
            if re.search(rf"\b{re.escape(word.lower())}\b", text.lower()):
                return cat_name
    return None

def get_manual_price(text):
    """Extracts numbers following 'under', 'below', etc."""
    match = re.search(r'(?:under|below|less than|<=?)\s*(\d+)', text.lower())
    return int(match.group(1)) if match else None

# ==========================================
# 2. MAIN ROUTING LOGIC
# ==========================================

async def handle_clothing_logic(client, phone_number, message_data, phone_number_id):
    keywords = client.get("keywords", {})
    
    # --- A. CHECK FOR BUTTON INTERACTION ---
    
    # If the user clicked "View More" (Pagination)
    if message_data.startswith("more_"):
        _, cat, prc, off = message_data.split("_")
        return await send_catalog_ui(
            client, phone_number, phone_number_id, 
            category=None if cat == "none" else cat,
            max_price=None if prc == "none" else int(prc),
            offset=int(off)
        )
        
    # If the user clicked "Buy Now" on a specific product
    if message_data.startswith("buy_"):
        product_id = message_data.split("buy_")[1]
        reply = f"Awesome choice! 🛍️ We are processing your order for item #{product_id}. A human agent will connect with you shortly for payment and delivery details."
        return await finalize(phone_number, reply, phone_number_id, "checkout_started")

    # --- B. TEXT INTENT CHECKING ---
    user_text = message_data.lower().strip()
    detected_cat = get_manual_category(user_text, keywords.get("categories", {}))
    max_price = get_manual_price(user_text)

    # RULE 1: If product/price mentioned -> Go straight to Catalog
    if detected_cat or max_price:
        return await send_catalog_ui(client, phone_number, phone_number_id, detected_cat, max_price, 0)

    # RULE 2: If greeting -> Send Welcome Message
    if any(re.search(rf"\b{re.escape(w)}\b", user_text) for w in keywords.get("greeting", [])):
        reply = client.get("intent_responses", {}).get("greeting")
        btns = [{"id": "more_none_none_0", "title": "🛍️ View All Items"}]
        return await finalize(phone_number, reply, phone_number_id, "greeting", buttons=btns)

    # --- C. AI FALLBACK (Last Resort) ---
    if client.get("features", {}).get("ai_fallback"):
        ai_reply = generate_replay(message_data, client.get("system_prompt"), phone_number)
        return await finalize(phone_number, ai_reply, phone_number_id, "ai_fallback")

    return {"status": "ignored"}

# ==========================================
# 3. CATALOG UI GENERATOR
# ==========================================

async def send_catalog_ui(client, phone_number, phone_id, category, max_price, offset):
    products = client.get("products", [])
    currency = client.get("ui", {}).get("currency", "₹")
    limit = client.get("ui", {}).get("max_items_per_message", 3)

    # Filter products
    filtered = [
        p for p in products 
        if (not category or p["category"] == category) and (not max_price or p["price"] <= max_price)
    ]

    if not filtered:
        return await finalize(phone_number, "Sorry, we don't have items matching that criteria right now.", phone_id, "no_results")

    # Slice for current page
    page_items = filtered[offset : offset + limit]
    
    # 1. SEND HEADER (Optional, but good for context)
    if offset == 0:
        header = f"👕 *{client['name']} Selection*\n"
        if category: header += f"Type: {category.capitalize()}\n"
        if max_price: header += f"Budget: {currency}{max_price}"
        send_whatsapp_message(to=phone_number, text=header)

    # 2. SEND INDIVIDUAL PRODUCT CARDS (The Catalogue UI)
    for p in page_items:
        item_text = f"*{p['name']}*\n💰 Price: {currency}{p['price']}\n📝 {p['description']}"
        item_buttons = [{"id": f"buy_{p['id']}", "title": "🛒 Buy Now"}]
        
        # This calls the updated whatsapp.py that supports image_url
        send_whatsapp_message(
            to=phone_number, 
            text=item_text, 
            buttons=item_buttons, 
            image_url=p['image_url']
        )

    # 3. SEND PAGINATION (View More)
    next_offset = offset + limit
    if next_offset < len(filtered):
        state_id = f"more_{category if category else 'none'}_{max_price if max_price else 'none'}_{next_offset}"
        btns = [{"id": state_id, "title": "⬇️ View More"}]
        more_text = f"We have {len(filtered) - next_offset} more items in this category!"
        return await finalize(phone_number, more_text, phone_id, "catalog_page", buttons=btns)
    else:
        end_text = "✅ *You've seen everything in this category!*"
        return await finalize(phone_number, end_text, phone_id, "catalog_end")

# ==========================================
# 4. FINALIZER HELPER
# ==========================================

async def finalize(phone_num, text, phone_id, status, buttons=None):
    """Sends a text/button message and saves to DB."""
    send_whatsapp_message(to=phone_num, text=text, buttons=buttons)
    save_message_to_db(phone_num, "assistant", text, phone_id)
    return {"status": status}