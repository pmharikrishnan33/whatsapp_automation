import re
from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db
from app.services.ai import generate_replay

# ==========================================
# 1. STRUCTURAL UTILITIES (0 TOKENS)
# ==========================================

def get_manual_category(text, categories_map):
    """Structural Check: Matches text against JSON category keywords."""
    for cat_name, synonyms in categories_map.items():
        if any(re.search(rf"\b{re.escape(word.lower())}\b", text.lower()) for word in synonyms):
            return cat_name
    return None

def get_manual_price(text):
    """Structural Check: Extracts price from phrases like 'under 500'."""
    match = re.search(r'(?:under|below|less than|<=?)\s*(\d+)', text.lower())
    return int(match.group(1)) if match else None

# ==========================================
# 2. THE MULTI-TENANT ROUTER
# ==========================================

async def handle_clothing_logic(client, phone_number, message_data, phone_number_id):
    features = client.get("features", {})
    menus = client.get("menus", {})
    keywords = client.get("keywords", {})
    user_text = message_data.lower().strip()
    
    # --- PHASE 1: GREETING & INTENT OVERRIDE ---
    is_greeting = any(re.search(rf"\b{re.escape(w)}\b", user_text) for w in keywords.get("greeting", []))
    
    if is_greeting or message_data == "menu_main":
        # Intent Override: Check if they mentioned a category or price in their "Hi"
        cat_check = get_manual_category(user_text, keywords.get("categories", {}))
        price_check = get_manual_price(user_text)
        
        if not (cat_check or price_check):
            # Clean Welcome Message (No initial buttons to save user steps)
            avail_cats = ", ".join([c.capitalize() for c in keywords.get("categories", {}).keys()])
            welcome_text = (
                f"Welcome to *{client.get('name')}*! 👔\n\n"
                f"We currently have: *{avail_cats}*.\n\n"
                "How can I help you? You can ask for a category (e.g., 'Show shirts'), "
                "set a budget (e.g., 'under 1000'), or ask for our 'Size Guide'."
            )
            return await finalize(phone_number, welcome_text, phone_number_id, "welcome_msg")

    # --- PHASE 2: SIZE & FIT QUIZ (Zero-Token) ---
    if message_data == "menu_size" or any(re.search(rf"\b{re.escape(w)}\b", user_text) for w in keywords.get("size_guide", [])):
        if features.get("size_guide_enabled"):
            menu_cfg = menus.get("size_guide", {})
            image_url = client.get("assets", {}).get("size_chart_url")
            send_whatsapp_message(phone_number, menu_cfg.get("text"), buttons=menu_cfg.get("buttons"), image_url=image_url)
            return {"status": "size_guide_sent"}

    if message_data.startswith("quiz_") and features.get("fit_quiz_enabled"):
        quiz = client.get("fit_quiz", {})
        if message_data == "quiz_start":
            return await finalize(phone_number, quiz.get("q1_text"), phone_number_id, "quiz_q1", buttons=quiz.get("brands"))
        if message_data.startswith("quiz_brand_"):
            brand = message_data.split("_")[2]
            text = quiz.get("q2_text", "").replace("{brand}", brand.capitalize())
            btns = [{"id": f"quiz_fit_{f['id_suffix']}_{brand}", "title": f["title"]} for f in quiz.get("fits", [])]
            return await finalize(phone_number, text, phone_number_id, "quiz_q2", buttons=btns)
        if message_data.startswith("quiz_fit_"):
            _, _, fit_pref, brand = message_data.split("_")
            size = quiz.get("logic_table", {}).get(f"{brand}_{fit_pref}", quiz.get("logic_table", {}).get("default", "M"))
            text = quiz.get("result_text", "").replace("{size}", size)
            return await finalize(phone_number, text, phone_number_id, "quiz_result", buttons=[{"id": "menu_catalog", "title": "🛍️ Browse Catalog"}])

    # --- PHASE 3: CATALOG & FILTERING (Zero-Token) ---
    detected_cat = get_manual_category(user_text, keywords.get("categories", {}))
    max_price = get_manual_price(user_text)

    if (message_data == "menu_catalog" or message_data.startswith("more_") or detected_cat or max_price):
        if features.get("catalog_enabled"):
            cat, prc, off = detected_cat, max_price, 0
            if message_data.startswith("more_"):
                _, cat_str, prc_str, off_str = message_data.split("_")
                cat, prc, off = (None if cat_str == "none" else cat_str), (None if prc_str == "none" else int(prc_str)), int(off_str)
            return await send_catalog_ui(client, phone_number, phone_number_id, cat, prc, off)

    if message_data.startswith("buy_"):
        product_id = message_data.split("buy_")[1]
        return await finalize(phone_number, f"🛍️ Order started for item #{product_id}. We'll contact you shortly!", phone_number_id, "checkout")

    # --- PHASE 4: LIMITED AI FALLBACK (Token Capped) ---
    if features.get("ai_fallback_enabled"):
        ai_reply = generate_replay(message_data, client.get("system_prompt"), phone_number)
        return await finalize(phone_number, ai_reply, phone_number_id, "ai_fallback")

    return await finalize(phone_number, "I'm not sure how to help. Try asking for a category like 'Shirts'!", phone_number_id, "fallback")

# ==========================================
# 3. CATALOG UI HELPER
# ==========================================

async def send_catalog_ui(client, phone_number, phone_id, category, max_price, offset):
    products = client.get("products", [])
    ui = client.get("ui", {})
    limit, currency = ui.get("max_items_per_message", 3), ui.get("currency", "₹")

    filtered = [p for p in products if (not category or p["category"] == category) and (not max_price or p["price"] <= max_price)]

    if not filtered:
        return await finalize(phone_number, f"No items found matching your filter.", phone_id, "no_results")

    if offset == 0:
        header = f"👕 *{client['name']} Catalog*\n" + (f"Type: {category.capitalize()}\n" if category else "") + (f"Budget: {currency}{max_price}" if max_price else "")
        send_whatsapp_message(phone_number, header)

    for p in filtered[offset : offset + limit]:
        text = f"*{p['name']}*\n💰 {currency}{p['price']}\n📝 {p['description']}"
        send_whatsapp_message(phone_number, text, buttons=[{"id": f"buy_{p['id']}", "title": "🛒 Buy Now"}], image_url=p['image_url'])

    next_off = offset + limit
    if next_off < len(filtered):
        state_id = f"more_{category if category else 'none'}_{max_price if max_price else 'none'}_{next_off}"
        return await finalize(phone_number, f"We have {len(filtered)-next_off} more items!", phone_id, "catalog_more", buttons=[{"id": state_id, "title": "⬇️ View More"}])
    
    return await finalize(phone_number, "✅ *End of collection.*", phone_id, "catalog_end", buttons=[{"id": "menu_main", "title": "🔙 Main Menu"}])

async def finalize(phone_num, text, phone_id, status, buttons=None):
    send_whatsapp_message(to=phone_num, text=text, buttons=buttons)
    save_message_to_db(phone_num, "assistant", text, phone_id)
    return {"status": status}