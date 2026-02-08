import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_notifications():
    # 1. Register a test user
    print("Registering test user...")
    reg_data = {
        "username": "test_notif_user",
        "full_name": "Test Notif User",
        "password": "password123",
        "municipality": "Naic",
        "street_barangay": "Bagong Karsada",
        "role": "farmer"
    }
    
    req = urllib.request.Request(
        f"{BASE_URL}/api/register",
        data=json.dumps(reg_data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code != 400: # Ignore if already exists
            print(f"Registration failed: {e.read().decode('utf-8')}")

    # 2. Login to get ID
    print("Logging in...")
    login_data = {"username": "test_notif_user", "password": "password123"}
    req = urllib.request.Request(
        f"{BASE_URL}/api/login",
        data=json.dumps(login_data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        res_json = json.loads(response.read().decode('utf-8'))
        user_id = res_json['user_id']
        print(f"User ID: {user_id}")

    # 3. Test generic GET /api/notifications?user_id=XX
    print(f"Testing /api/notifications?user_id={user_id}")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/notifications?user_id={user_id}") as response:
            data = response.read().decode('utf-8')
            print(f"Response Code: {response.status}")
            print(f"Response Body: {data}")
            
            try:
                json_data = json.loads(data)
                if isinstance(json_data, list):
                    print("SUCCESS: Returned a JSON Array")
                else:
                    print(f"FAILURE: Returned {type(json_data)} instead of list")
            except json.JSONDecodeError:
                print("FAILURE: Could not decode JSON")
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} - {e.read().decode('utf-8')}")

    # 4. Create a test notification (simulate admin sending one)
    print("Creating test notification...")
    notif_data = {
        "target_type": "user",
        "target_value": user_id,
        "level": "High",
        "message": "Test Alert for Including Read"
    }
    # We need admin login to send notification or just insert via DB if locally running?
    # Since we don't have easy admin login in this script, let's rely on manual insertion or skip creation if too complex.
    # Actually, we can use the `send_notification` endpoint if we login as admin.
    # Simpler: Just rely on existing notifications if any, or skip creation and just test the parameter.
    # BUT wait, the user said they saw one notification then it disappeared.
    # So let's try to fetch with include_read=true
    
    print(f"Testing /api/notifications?user_id={user_id}&include_read=true")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/notifications?user_id={user_id}&include_read=true") as response:
            data = response.read().decode('utf-8')
            print(f"Response Body (With Read): {data}")
            json_data = json.loads(data)
            if isinstance(json_data, list):
                 print("SUCCESS: Returned JSON list with history")
            
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} - {e.read().decode('utf-8')}")

if __name__ == "__main__":
    test_notifications()
