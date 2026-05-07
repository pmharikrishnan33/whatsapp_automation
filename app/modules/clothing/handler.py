import re
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import generate_replay

# --- MANUAL RULE CHECKS ---

def get_manual_category(text, categories_map):
    """Manual Check: Exact word boundary matching for categories."""
    for cat_name, synonyms in categories_map.items():
        for word in synonyms:
            if re.search(rf"\b{re.escape(word.lower())}\b", text.lower()):
                return cat_name
    return None

def get_manual_price(text):
    """Manual Check: Regex for price extraction (e.g., 'under 600')."""
    match = re.search(r'(?:under|below|less than|<=?)\s*(\d+)', text.lower())
    return int(match.group(1)) if match else None

# --- MAIN LOGIC ---

async def handle_clothing_logic(client, phone_number, message_data, phone_number_id):
    keywords = client.get("keywords", {})
    
    # 1. CHECK FOR BUTTON INTERACTION (Pagination)
    if message_data.startswith("more_"):
        # Pattern: more_{category}_{price}_{offset}
        _, cat, prc, off = message_data.split("_")
        return await send_catalog_ui(
            client, phone_number, phone_number_id, 
            category=None if cat == "none" else cat,
            max_price=None if prc == "none" else int(prc),
            offset=int(off)
        )

    # 2. MANUAL INTENT CHECKING
    user_text = message_data.lower().strip()
    detected_cat = get_manual_category(user_text, keywords.get("categories", {}))
    max_price = get_manual_price(user_text)

    # RULE: If user mentions a product/price, bypass greeting and show catalog
    if detected_cat or max_price:
        return await send_catalog_ui(client, phone_number, phone_number_id, detected_cat, max_price, 0)

    # 3. GREETING CHECK (Only if no product intent found)
    if any(re.search(rf"\b{re.escape(w)}\b", user_text) for w in keywords.get("greeting", [])):
        reply = client.get("intent_responses", {}).get("greeting")
        return await finalize(phone_number, reply, phone_number_id, "greeting")

    # 4. AI FALLBACK (Last Resort)
    if client.get("features", {}).get("ai_fallback"):
        ai_reply = generate_replay(message_data, client.get("system_prompt"), phone_number)
        return await finalize(phone_number, ai_reply, phone_number_id, "ai_fallback")

    return {"status": "unhandled"}

# --- CATALOG UI & PAGINATION ENGINE ---

async def send_catalog_ui(client, phone_number, phone_id, category, max_price, offset):
    products = client.get("products", [])
    currency = client.get("ui", {}).get("currency", "₹")
    limit = client.get("ui", {}).get("max_items_per_message", 3)

    # Filter logic
    filtered = [
        p for p in products 
        if (not category or p["category"] == category) and (not max_price or p["price"] <= max_price)
    ]

    if not filtered:
        return await finalize(phone_number, "No items found matching your request.", phone_id, "no_results")

    # Slice for pagination
    page_items = filtered[offset : offset + limit]
    
    # Build UI
    ui_text = f"👕 *{client['name']} Selection*\n"
    if category: ui_text += f"Type: {category.capitalize()}\n"
    if max_price: ui_text += f"Budget: {currency}{max_price}\n"
    ui_text += "__________________________\n\n"

    for p in page_items:
        ui_text += f"*{p['name']}*\n"
        ui_text += f"💰 {currency}{p['price']}\n"
        ui_text += f"📝 {p['description']}\n"
        ui_text += f"🔗 {p['image_url']}\n\n"

    # Button Logic
    btns = None
    next_offset = offset + limit
    if next_offset < len(filtered):
        # Store state in button ID for the next request
        state_id = f"more_{category if category else 'none'}_{max_price if max_price else 'none'}_{next_offset}"
        btns = [{"id": state_id, "title": "⬇️ View More"}]
        ui_text += f"_+{len(filtered) - next_offset} more items available._"
    else:
        ui_text += "✅ *You've seen everything in this category!*"

    return await finalize(phone_number, ui_text, phone_id, "catalog_page", btns)

async def finalize(phone_num, text, phone_id, status, buttons=None):
    send_whatsapp_message(phone_num, text, buttons)
    save_message_to_db(phone_num, "assistant", text, phone_id)
    return {"status": status}