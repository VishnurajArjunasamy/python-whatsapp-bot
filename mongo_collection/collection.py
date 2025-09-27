import pymongo
import certifi
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv

load_dotenv()
uri = f"mongodb+srv://{os.getenv("DB_USERNAME")}:{os.getenv('DB_PASSWORD')}@cluster0.nqgvp.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def get_collection():
    mongo_client = pymongo.MongoClient(uri,server_api=ServerApi('1'),tlsCAFile=certifi.where())
    db = mongo_client["whatsapp_bot"]
    collection = db["user_sessions"]
    collection.create_index([("user_id", 1)])
    collection.create_index([("conversations.conversation_id", 1)])
    return collection