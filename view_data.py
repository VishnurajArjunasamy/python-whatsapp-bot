from pymongo import MongoClient
import pprint


# Connect to local MongoDB
client = MongoClient("mongodb://localhost:27017/")

# Select your database and collection
db = client["whatsapp_bot"]
collection = db["user_sessions"]

# Fetch all documents
all_users = collection.find()

print("==== Stored WhatsApp Bot Messages ====")
for user in all_users:
    pprint.pprint(user)