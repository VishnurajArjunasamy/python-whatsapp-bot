import logging
from flask import current_app, jsonify
import json
import requests
from mongo_collection.collection import get_collection
# from app.services.openai_service import generate_response
import re
from datetime import datetime
from bson import ObjectId
import base64


# simple in-memory state
user_states = {}
collection = get_collection()

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def download_audio(media_id):
    url = f"https://graph.facebook.com/v17.0/{media_id}"
    headers = {"Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}"}
    res = requests.get(url, headers=headers).json()
    media_url = res["url"]
    audio_data = requests.get(media_url, headers=headers).content
    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
    return audio_base64


def handle_text(user, text=None):
    state = user_states.get(user, "START")
    user_data = collection.find_one({"user_id": user}) or {}
    
    if text == "/start":
        # Create a new conversation
        conversation_id = ObjectId()
        conversation = {
            "conversation_id": conversation_id,
            "started_at": datetime.utcnow(),
            "status": "in_progress",
            "data": {}
        }
        
        # Add conversation to user's conversations array
        collection.update_one(
            {"user_id": user},
            {
                "$push": {"conversations": conversation},
                "$set": {"current_conversation_id": conversation_id}
            },
            upsert=True
        )
        
        response = "Hi! Welcome! What's your name?"
        user_states[user] = "WAITING_NAME"
        data = get_text_message_input(user, response)
        send_message(data)
        return

    # Get current conversation
    current_conversation_id = user_data.get("current_conversation_id")
    if not current_conversation_id:
        response = "Please start a new conversation with /start"
        data = get_text_message_input(user, response)
        send_message(data)
        return

    if state == "WAITING_NAME":
        if not isinstance(text,str):
            response = "Please enter a valid input"
            data = get_text_message_input(user, response)
            send_message(data)
            return
        collection.update_one(
            {
                "user_id": user,
                "conversations.conversation_id": current_conversation_id
            },
            {
                "$set": {
                    "conversations.$.data.name": text,
                    "conversations.$.last_updated": datetime.utcnow()
                }
            }
        )
        response = f"Nice to meet you {text}! Please enter your age:"
        user_states[user] = "WAITING_AGE"
        data = get_text_message_input(user, response)
        send_message(data)
        return

    if state == "WAITING_AGE":
        if not text.isdigit():
            response = "Please enter a valid age (numbers only)"
            data = get_text_message_input(user, response)
            send_message(data)
            return
            
        collection.update_one(
            {
                "user_id": user,
                "conversations.conversation_id": current_conversation_id
            },
            {
                "$set": {
                    "conversations.$.data.age": int(text),
                    "conversations.$.last_updated": datetime.utcnow()
                }
            }
        )
        response = "What's your location (city)?"
        user_states[user] = "WAITING_LOCATION"
        data = get_text_message_input(user, response)
        send_message(data)
        return

    if state == "WAITING_LOCATION":
        if not isinstance(text,str):
            response = "Please enter a valid input"
            data = get_text_message_input(user, response)
            send_message(data)
            return
        collection.update_one(
            {
                "user_id": user,
                "conversations.conversation_id": current_conversation_id
            },
            {
                "$set": {
                    "conversations.$.data.location": text,
                    "conversations.$.last_updated": datetime.utcnow(),
                    # "conversations.$.status": "completed"
                }
            }
        )
        response = f"Enter voice message";
        user_states[user]="WAITING_VOICE"
        data = get_text_message_input(user,response)
        send_message(data)
        return
    
    if state == "WAITING_VOICE":
        if text :
            response = "Please enter a valid Voice Message"
            data = get_text_message_input(user, response)
            send_message(data)
            return

    response = "Please start a new conversation with /start"
    data = get_text_message_input(user,response)
    send_message(data)
    return


def handle_voice(user, media_id):
    state = user_states.get(user, "START")
    user_data = collection.find_one({"user_id": user}) or {}

    # Get current conversation
    current_conversation_id = user_data.get("current_conversation_id")
    if not current_conversation_id:
        response = "Please start a new conversation with /start"
        data = get_text_message_input(user, response)
        send_message(data)
        return

    if state == "WAITING_VOICE":
        audio_base64 = download_audio( media_id)
        collection.update_one(
            {
                "user_id": user,
                "conversations.conversation_id": current_conversation_id
            },
            {
                "$set": {
                    "conversations.$.data.audio": audio_base64,
                    "conversations.$.last_updated": datetime.utcnow(),
                    "conversations.$.status": "completed"
                }
            }
        )
        user_doc = collection.find_one(
            {
                "user_id": user,
                "conversations.conversation_id": current_conversation_id
            },
            {"conversations.$": 1}
        )
        conv_data = user_doc["conversations"][0]["data"]
        
        response = f"Perfect! Thank you for the response."
        user_states[user] = "COMPLETED"
        data = get_text_message_input(user, response)
        send_message(data)
        return


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    # message_body = message["text"]["body"]
    receipient_waid = message['from']

    # TODO: implement custom function here
    if message['type']=='text':
        text = message['text']['body'].strip().lower()
        response = handle_text(receipient_waid,text)

    if message['type'] == 'audio':
       response = handle_voice(receipient_waid,message['audio']['id'])


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
