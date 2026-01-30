import urllib.request
import urllib.parse
import json
import http.cookiejar

BASE_URL = "http://127.0.0.1:5000"

# Setup cookie jar for session management
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
urllib.request.install_opener(opener)

def post_json(url, data):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with opener.open(req) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')

def test_admin_flow():
    # 1. Login as Admin (created in previous step)
    print("Logging in as Admin...")
    login_data = {"username": "admin", "password": "admin123"}
    status, text = post_json(f"{BASE_URL}/api/login", login_data)
    print(f"Admin Login: {status}")
    
    if status != 200:
        print("Admin login failed. Aborting.")
        return

    # 2. Access Admin Dashboard (GET)
    print("Accessing Admin Dashboard...")
    try:
        with opener.open(f"{BASE_URL}/admin/dashboard") as response:
            print(f"Dashboard Access: {response.status}")
            content = response.read().decode('utf-8')
            if "Admin Console" in content:
                print("Verified 'Admin Console' text in response.")
            else:
                print("WARNING: 'Admin Console' not found in response.")
    except urllib.error.HTTPError as e:
        print(f"Dashboard Access Failed: {e.code}")

    # 3. Create a dummy record to delete (via API as a user)
    # We need to log in as a farmer first, but that clears the admin session in simple cookie jar usage if we use same opener?
    # Actually, Flask-Login uses session cookies. Overwriting them logs us out.
    # So we need a separate opener for the farmer or re-login.
    
    # Let's use a separate opener for the farmer actions
    farmer_cj = http.cookiejar.CookieJar()
    farmer_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(farmer_cj))
    
    print("Creating dummy record as Farmer...")
    # Login Farmer
    req = urllib.request.Request(
        f"{BASE_URL}/api/login", 
        data=json.dumps({"username": "testfarmer_urllib", "password": "password123"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with farmer_opener.open(req) as response:
        farmer_data = json.loads(response.read().decode('utf-8'))
        user_id = farmer_data['user_id']
        
    # Upload Record
    # Simplified multipart for brevity manually constructed
    boundary = '---BOUNDARY'
    data_content = f'--{boundary}\r\nContent-Disposition: form-data; name="user_id"\r\n\r\n{user_id}\r\n'
    data_content += f'--{boundary}\r\nContent-Disposition: form-data; name="insect_name"\r\n\r\nTestInsect\r\n'
    data_content += f'--{boundary}\r\nContent-Disposition: form-data; name="confidence"\r\n\r\n0.99\r\n'
    data_content += f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="del.jpg"\r\nContent-Type: image/jpeg\r\n\r\nfakecontent\r\n'
    data_content += f'--{boundary}--\r\n'
    
    req = urllib.request.Request(
        f"{BASE_URL}/api/sync/identify",
        data=data_content.encode('utf-8'),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )
    with farmer_opener.open(req) as response:
         print(f"Record Created: {response.status}")

    # 4. Admin: Delete the record (We don't know the ID easily without parsing HTML or DB query, 
    # but since it's the latest, we can guess or for this test script, we might trust specific ID if DB was clean
    # or skip ID specific check and just check if Delete endpoint is reachable/protected)
    
    # For robust testing without DB access in script, we'll try to delete ID=1 (if created early)
    # or just skip exact ID deletion and focus on route access.
    
    # Let's try to delete ID 1 (Assuming from previous tests it exists)
    print("Testing Delete Record (ID: 1)...")
    try:
        # POST to delete
        req = urllib.request.Request(f"{BASE_URL}/admin/delete_record/1", method='POST')
        with opener.open(req) as response:
            print(f"Delete Record ID 1: {response.status} (Note: Might be 404 if already deleted, but 200/302 means auth ok)")
    except urllib.error.HTTPError as e:
        print(f"Delete Failed: {e.code}")

    # 5. Admin: Reset Password for Farmer
    print(f"Testing Reset Password for User ID {user_id}...")
    try:
        req = urllib.request.Request(f"{BASE_URL}/admin/reset_password/{user_id}", method='POST')
        with opener.open(req) as response:
            print(f"Reset Password: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"Reset Password Failed: {e.code}")

if __name__ == "__main__":
    test_admin_flow()
