import requests
import random
import string

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# Try to add a user via API
url = "http://localhost:6565/api/login"
r = requests.post(url, data={"username": "Admin", "password": "Amir"})
token = r.json()["access_token"]

username = f"test_{random_string()}"
print(f"Adding user {username}...")

url = "http://localhost:6565/api/users"
headers = {"Authorization": f"Bearer {token}"}
data = {
    "name": "Subagent Test",
    "phone": "123456789",
    "username": username,
    "password": "password123"
}
r = requests.post(url, json=data, headers=headers)
print(f"Add User Result: {r.status_code}")
print(r.text)
