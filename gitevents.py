import os
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import json

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "github_webhook_db")
COLLECTION_NAME = "events"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
events_collection = db[COLLECTION_NAME]

print(f"Connected to MongoDB: {MONGO_URI}, Database: {MONGO_DB_NAME}")

def store_event(event_data):
    try:
        events_collection.insert_one(event_data)
        print(f"Successfully stored event: {event_data['event_type']}")
    except Exception as e:
        print(f"Error storing event to MongoDB: {e}")

@app.route('/webhook', methods=['POST'])
def github_webhook():
    if request.method == 'POST':
        event_type = request.headers.get('X-GitHub-Event')
        payload = request.json

        if not payload:
            print("Recieved empty payload")
            return jsonify({"status": "error", "message": "No payload recieved"}), 400
        print(f"Recieved Github event: {event_type}")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        event_to_store = None

        if event_type == 'push':
            author = payload['pusher']['name']
            to_branch = payload['ref'].split('/')[-1]
            timestamp_str = payload['head_commit']['timestamp'] if payload.get('head_commit') else datetime.utcnow().isoformat() + "Z"
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            event_to_store = {
                "event_type": "PUSH",
                "author": author,
                "to_branch": to_branch,
                "timestamp": timestamp
            }

            print(f"Processed push event: {event_to_store}")

        elif event_type == 'pull_request':
            action = payload['action']
            pull_request = payload['pull_request']

            if action == 'opened':
                author = pull_request['user']['login']
                from_branch = pull_request['head']['ref']
                to_branch = pull_request['base']['ref']
                timestamp_str = pull_request['created_at']
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                event_to_store = {
                    "event_type": "PULL_REQUEST",
                    "author": author,
                    "from_branch": from_branch,
                    "to_branch": to_branch,
                    "timestamp": timestamp
                }

                print(f"Processed PULL_REQUEST (opened) event: {event_to_store}")

            elif action == 'closed' and pull_request.get('merged'):
                author = pull_request['merged_by']['login'] if pull_request.get('merged_by') else pull_request['user']['login']
                from_branch = pull_request['head']['ref']
                to_branch = pull_request['base']['ref']
                timestamp_str = pull_request['merged_at']
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                event_to_store = {
                    "event_type": "MERGE",
                    "author": author,
                    "from_branch": from_branch,
                    "to_branch": to_branch,
                    "timestamp": timestamp
                }
                print(f"Processed MERGE event: {event_to_store}")
            else:
                print(f"Unhandled pull_request action: {action}")
        else:
            print(f"Unhandled github event type: {event_type}")
            return jsonify({"status": "ignored", "message": f"Unhandled event type: {event_type}"}), 200
        
        if event_to_store:
            store_event(event_to_store)
            return jsonify({"status": "success", "message": f"Event {event_type} processed and stored"}), 200
        else:
            return jsonify({"status": "ignored", "message": "No relevant event data to store"}), 200

    return jsonify({"status": "error", "message": "Method not allowed"}), 405

@app.route('/events', methods=['GET'])
def get_events():
    try:
        latest_events = list(events_collection.find().sort("timestamp", -1).limit(20))

        formatted_events = []

        for event in latest_events:
            event['timestamp'] = event['timestamp'].isoformat()
            event.pop('_id', None)
            formatted_events.append(event)

        return jsonify(formatted_events)
    
    except Exception as e:
        print(f"Error fetching events from MongoDB: {e}")
        return jsonify({"status": "error", "message": "Could not fetch events"}), 500
    
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)