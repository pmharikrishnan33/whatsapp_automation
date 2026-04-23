# Simple in-memory storage (per user)

conversation_memory = {}

def get_history(phone_number: str):
    return conversation_memory.get(phone_number, [])

def add_to_history(phone_number: str, role: str, message: str):
    
    if phone_number not in conversation_memory:
        conversation_memory[phone_number] = []

    conversation_memory[phone_number].append({
        "role": role,
        "content": message
    })

    # Optional: limit memory size
    conversation_memory[phone_number] = conversation_memory[phone_number][-10:]