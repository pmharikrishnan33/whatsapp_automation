import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from app.config import MONGO_URI

uri=MONGO_URI

if not uri:
    raise Exception("MONGO_URI not found in environment variables")

# Create MongoDB client
client = MongoClient(uri, server_api=ServerApi('1'))

# Select database
db = client["zyphor"]

# Collections
clients_collection = db["clients"]
messages_collection = db["messages"]  # optional (for chat history later)

# Optional: test connection (runs once on import)
try:
    client.admin.command('ping')
    print("MongoDB connected successfully")
except Exception as e:
    print("MongoDB connection error:", e)