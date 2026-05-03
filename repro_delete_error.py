import requests

# Try to delete an organization via API
url = "http://localhost:6565/api/login"
r = requests.post(url, data={"username": "Admin", "password": "Amir"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get list of orgs
r = requests.get("http://localhost:6565/api/organizations", headers=headers)
orgs = r.json()
print(f"Orgs: {[o['id'] for o in orgs]}")

if orgs:
    last_id = orgs[0]["id"]
    print(f"Deleting org {last_id}...")
    r = requests.delete(f"http://localhost:6565/api/organizations/{last_id}", headers=headers)
    print(f"Delete Result: {r.status_code}")
    print(r.text)
else:
    print("No organizations to delete.")
