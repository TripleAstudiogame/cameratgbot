import urllib.request, json
import app, db

import threading, uvicorn, time
def run_server():
    uvicorn.run(app.app, host="127.0.0.1", port=8006, log_level="error")

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)

token = app.create_token({'sub': 'Amir', 'role': 'admin'})
req = urllib.request.Request(
    'http://127.0.0.1:8006/api/users',
    data=b'{"name":"Amir","phone":"+998","username":"Amir123","password":"123"}',
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    print("Success:", resp.read())
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print("Body:", e.read().decode('utf-8'))
