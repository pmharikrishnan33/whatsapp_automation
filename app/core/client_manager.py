from app.core.mongo import clients_collection

def get_client_config(phone_number_id: str):
    # MongoDB will return all fields including order_enabled and intent_responses
    client = clients_collection.find_one({
        "phone_number_id": phone_number_id
    })

    if client:
        client["_id"] = str(client["_id"])
    
    return client