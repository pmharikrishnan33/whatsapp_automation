from app.core.whatsapp import send_whatsapp_message
from app.core.memory import save_message_to_db

async def handle_clothing_logic(client, phone_number, text, phone_number_id):
    # Simple test logic specifically for clothing
    save_message_to_db(phone_number, "user", text, phone_number_id)
    
    shop_name = client.get("name", "The Clothing Store")
    reply = f"👔 Welcome to {shop_name}! This is the Clothing Module test.\n\nYou sent: '{text}'"
    
    send_whatsapp_message(phone_number, reply)
    save_message_to_db(phone_number, "assistant", reply, phone_number_id)
    
    return {"status": "clothing_test_success"}