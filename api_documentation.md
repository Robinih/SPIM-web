# SPIM API Documentation for Android Integration

This document outlines how to connect the Android Application to the SPIM Backend.

## Base URL
- **Local Testing (Emulator)**: `http://10.0.2.2:5000`
- **Physical Device**: `http://<YOUR_LAPTOP_IP>:5000` (e.g., `192.168.1.5:5000`)
  - *Ensure valid IP and that both devices are on the same Wi-Fi.*

## Authentication
The API uses **Session Cookies** for web browser routes but returns a `user_id` for API calls.
For the Android App:
1.  **Register/Login** to get the `user_id`.
2.  Store `user_id` locally (Shared Preferences).
3.  Send `user_id` as a form field in data sync requests.

---

## 1. User Registration
**Endpoint**: `POST /api/register`
**Content-Type**: `application/json`

**Request Body**:
```json
{
  "username": "juan_delacruz",
  "full_name": "Juan Dela Cruz",
  "password": "securepassword",
  "municipality": "Naic",
  "street_barangay": "Bagong Karsada",
  "latitude": 14.320,  // Optional (Double)
  "longitude": 120.764 // Optional (Double)
}
```

**Response (201 Created)**:
```json
{
  "message": "User registered successfully"
}
```

---

## 2. User Login
**Endpoint**: `POST /api/login`
**Content-Type**: `application/json`

**Request Body**:
```json
{
  "username": "juan_delacruz",
  "password": "securepassword"
}
```

**Response (200 OK)**:
```json
{
  "message": "Login successful",
  "user_id": 1,
  "role": "farmer"
}
```
> **Action**: Save `user_id` in app preference `KEY_USER_ID`.

---

## 3. Sync Identification (Single Insect)
**Endpoint**: `POST /api/sync/identify`
**Content-Type**: `multipart/form-data`

**Form Fields**:
- `user_id`: (Integer) The ID saved from login.
- `insect_name`: (String) e.g., "Aphids"
- `confidence`: (Float) e.g., 0.95
- `image`: (File) The captured image file.

**Response (201 Created)**:
```json
{
  "message": "Detection saved"
}
```

---

## 4. Sync Counting (Multiple Insects)
**Endpoint**: `POST /api/sync/count`
**Content-Type**: `multipart/form-data`

**Form Fields**:
- `user_id`: (Integer) The ID saved from login.
- `total_count`: (Integer) Total insects detected.
- `breakdown`: (JSON String) e.g., `{"Aphids": 5, "Ladybug": 2}`
- `image`: (File) The overlaid image file.

**Response (201 Created)**:
```json
{
  "message": "Count record saved"
}
```

---

## 5. Dashboard Statistics
**Endpoint**: `GET /api/stats/dashboard`

**Response (200 OK)**:
```json
{
  "pests": 150,
  "beneficials": 45
}
```
> **Action**: Use these values to populate the Pie Chart / Dashboard in the Generic App.

---

## 6. Fetch Notifications (Alerts)
**Endpoint**: `GET /api/notifications`
**Query Parameters**:
- `user_id`: (Integer) The ID of the logged-in user.
- `include_read`: (Boolean, Optional) Set to `true` to fetch ALL notifications (history). Default is `false` (Unread Only).

**Example Request**:
`GET http://<IP>:5000/api/notifications?user_id=1&include_read=true`

**Response (200 OK)**:
Always returns a JSON Array `[]`, even if empty.
```json
[
  {
    "id": 1,
    "message": "High Pest Activity Detected! Please check your crops.",
    "level": "High",  // "High", "Medium", "Low"
    "timestamp": "2023-10-27 08:30",
    "is_read": false,
    "from_user": "System" // or "Juan Dela Cruz"
  },
  {
    "id": 2,
    "message": "Typhoon incoming tomorrow.",
    "level": "Medium",
    "timestamp": "2023-10-26 14:00",
    "is_read": true,
    "from_user": "System"
  }
]
```
> **Action**:
> - Poll this endpoint periodically (e.g., every 5-10 minutes) or on app launch.
> - Display "High" alerts with **Red** styling and "Medium/Low" with **Yellow/Info** styling.
> - Show a system notification (Push Notification style) using the `message`.
> - Use `include_read=true` to show a "History" tab in the app.
