import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENTS_FILE = os.path.join(BASE_DIR, "clients.json")

def get_client_config(phone_number: str):

    with open(CLIENTS_FILE, "r") as file:
        data = json.load(file)

    return data.get(phone_number)