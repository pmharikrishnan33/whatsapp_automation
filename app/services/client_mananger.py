from app.db.mongo import clients_collection

def get_client_config(phone_number_id: str):
    client = clients_collection.find_one({
        "phone_number_id": phone_number_id
    })

    if client:
        client["_id"] = str(client["_id"])  # convert ObjectId to string

    return client