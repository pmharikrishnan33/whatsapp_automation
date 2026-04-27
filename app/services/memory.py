from datetime import datetime, timedelta
from app.db.mongo import messages_collection, orders_collection, clients_collection

# In-memory storage for non-persistent workflow states (per user)
conversation_states = {}

# Global Country Rates in INR (per 24-hour conversation)
COUNTRY_RATES = {
    "91": 0.80,    # India
    "1": 1.50,     # USA
    "default": 1.00 
}

# --- DATABASE STORAGE FUNCTIONS ---

def save_message_to_db(phone_number, role, message, phone_number_id):
    """Stores every interaction in the messages collection."""
    messages_collection.insert_one({
        "phone_number": phone_number,
        "phone_number_id": phone_number_id,
        "role": role,
        "content": message,
        "timestamp": datetime.utcnow()
    })

def save_order_to_db(phone_number, order_details, customer_info, phone_number_id):
    """Stores the finalized order in the orders collection."""
    orders_collection.insert_one({
        "phone_number": phone_number,
        "phone_number_id": phone_number_id,
        "items": order_details,
        "customer_name": customer_info.get("name"),
        "location": customer_info.get("location"),
        "status": "pending",
        "timestamp": datetime.utcnow()
    })

# --- STATE & HISTORY MANAGEMENT ---

def get_state(phone_number: str):
    """Retrieves the current workflow state (e.g., AWAITING_ITEMS)."""
    return conversation_states.get(phone_number, {}).get("state", "IDLE")

def set_state(phone_number: str, state: str):
    """Sets the current workflow state for a user."""
    if phone_number not in conversation_states:
        conversation_states[phone_number] = {"history": [], "state": "IDLE"}
    conversation_states[phone_number]["state"] = state

def get_history(phone_number: str):
    """Gets recent history for flow-specific logic (like pending items)."""
    return conversation_states.get(phone_number, {}).get("history", [])

def add_to_history(phone_number: str, role: str, message: str):
    """Adds a message to the temporary session history."""
    if phone_number not in conversation_states:
        conversation_states[phone_number] = {"history": [], "state": "IDLE"}
    
    conversation_states[phone_number]["history"].append({
        "role": role,
        "content": message
    })
    # Keep last 10 session events
    conversation_states[phone_number]["history"] = conversation_states[phone_number]["history"][-10:]

# --- CREDIT & CONVERSATION TRACKING ---

def manage_client_credit(phone_number: str, phone_number_id: str):
    """Silently manages 24-hour windows and credit limits for clients."""
    client = clients_collection.find_one({"phone_number_id": phone_number_id})
    if not client:
        return

    # 1. Reset logic: Reset counters if a new month has started
    current_month = datetime.utcnow().strftime("%Y-%m")
    if client.get("last_reset_month") != current_month:
        clients_collection.update_one(
            {"phone_number_id": phone_number_id},
            {
                "$set": {
                    "current_month_spend": 0,
                    "free_conversations_used": 0,
                    "last_reset_month": current_month
                }
            }
        )

    # 2. Check 24-hour window: Find the last message sent BY the assistant
    last_assistant_msg = messages_collection.find_one(
        {"phone_number": phone_number, "role": "assistant"},
        sort=[("timestamp", -1)]
    )
    
    is_new_window = True
    if last_assistant_msg:
        time_diff = datetime.utcnow() - last_assistant_msg["timestamp"]
        if time_diff < timedelta(hours=24):
            is_new_window = False

    # 3. Process Charge for a New Conversation Window
    if is_new_window:
        free_used = client.get("free_conversations_used", 0)
        
        if free_used < 1000:
            # Still in free tier
            clients_collection.update_one(
                {"phone_number_id": phone_number_id},
                {"$inc": {"free_conversations_used": 1}}
            )
        else:
            # Over 1000 conversations: Apply country-based charge in INR
            country_code = "91" if phone_number.startswith("91") else "1" if phone_number.startswith("1") else "default"
            charge = COUNTRY_RATES.get(country_code, COUNTRY_RATES["default"])
            
            clients_collection.update_one(
                {"phone_number_id": phone_number_id},
                {"$inc": {"current_month_spend": charge}}
            )