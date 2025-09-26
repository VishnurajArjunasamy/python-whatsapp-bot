import pymongo

def get_collection():
    mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = mongo_client["whatsapp_bot"]
    collection = db["user_sessions"]
    collection.create_index([("user_id", 1)])
    collection.create_index([("conversations.conversation_id", 1)])
    return collection