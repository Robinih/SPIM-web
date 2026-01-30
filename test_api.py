import urllib.request
import urllib.parse
import json
import base64
import time

BASE_URL = "http://127.0.0.1:5000"
COOKIE = None

def get_opener():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    return opener

OPENER = get_opener()

def post_json(url, data):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with OPENER.open(req) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')

def post_multipart(url, fields, files):
    boundary = '---BOUNDARY'
    body = []
    
    for key, value in fields.items():
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="{key}"')
        body.append('')
        body.append(str(value))
        
    for key, (filename, content, mimetype) in files.items():
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"')
        body.append(f'Content-Type: {mimetype}')
        body.append('')
        if isinstance(content, str):
            body.append(content)
        else:
            # We need to handle bytes differently if we were concatenating bytes
            # For simplicity in this text-based builder, let's assume content is bytes but we decode for the body structure or write bytes.
            # Writing mixed bytes/str is annoying in Python.
            # Let's simple way: read mocked content as string/bytes
            pass
            
    # For this simple test, I'll encode everything to bytes
    
    body_bytes = []
    for key, value in fields.items():
        body_bytes.append(f'--{boundary}'.encode())
        body_bytes.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        body_bytes.append(b'')
        body_bytes.append(str(value).encode())
        
    for key, (filename, content, mimetype) in files.items():
        body_bytes.append(f'--{boundary}'.encode())
        body_bytes.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode())
        body_bytes.append(f'Content-Type: {mimetype}'.encode())
        body_bytes.append(b'')
        if isinstance(content, bytes):
            body_bytes.append(content)
        else:
            body_bytes.append(content.encode())
            
    body_bytes.append(f'--{boundary}--'.encode())
    
    payload = b'\r\n'.join(body_bytes)
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )
    
    try:
        with OPENER.open(req) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')

def test_flow():
    # 1. Register
    print("Testing Registration...")
    reg_data = {
        "username": "testfarmer_urllib",
        "full_name": "Test Farmer",
        "password": "password123",
        "municipality": "Naic",
        "street_barangay": "Barangay 1",
        "role": "farmer",
        "latitude": 14.3,
        "longitude": 120.8
    }
    status, text = post_json(f"{BASE_URL}/api/register", reg_data)
    print(f"Register: {status} - {text}")
    
    # 2. Login
    print("Testing Login...")
    login_data = {"username": "testfarmer_urllib", "password": "password123"}
    status, text = post_json(f"{BASE_URL}/api/login", login_data)
    print(f"Login: {status} - {text}")
    
    try:
        res_json = json.loads(text)
        user_id = res_json.get('user_id')
    except:
        print("Login failed to parse JSON")
        return

    # 3. Test Identify (Pest)
    print("Testing Sync Identify (Pest)...")
    with open('test_image.jpg', 'rb') as f:
        img_data = f.read()
        
    files = {'image': ('pest.jpg', img_data, 'image/jpeg')}
    fields = {'user_id': user_id, 'insect_name': 'Aphids', 'confidence': 0.95}
    status, text = post_multipart(f"{BASE_URL}/api/sync/identify", fields, files)
    print(f"Identify (Pest): {status} - {text}")

    # 4. Test Identify (Beneficial)
    print("Testing Sync Identify (Beneficial)...")
    files = {'image': ('beneficial.jpg', img_data, 'image/jpeg')}
    fields = {'user_id': user_id, 'insect_name': 'Pygmy Grasshopper', 'confidence': 0.88}
    status, text = post_multipart(f"{BASE_URL}/api/sync/identify", fields, files)
    print(f"Identify (Beneficial): {status} - {text}")

    # 5. Test Count
    print("Testing Sync Count...")
    files = {'image': ('count.jpg', img_data, 'image/jpeg')}
    fields = {
        'user_id': user_id, 
        'total_count': 15, 
        'breakdown': '{"Aphids": 10, "Pygmy Grasshopper": 5}'
    }
    status, text = post_multipart(f"{BASE_URL}/api/sync/count", fields, files)
    print(f"Count: {status} - {text}")

    # 6. Test Stats Dashboard
    print("Testing Stats Dashboard...")
    # Need to keep session cookies
    try:
        with OPENER.open(f"{BASE_URL}/api/stats/dashboard") as response:
            print(f"Stats: {response.status} - {response.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"Stats Error: {e.code} - {e.read().decode('utf-8')}")

if __name__ == "__main__":
    test_flow()
