import subprocess
import time
import urllib.request
import app

# Start the actual app.py using subprocess
p = subprocess.Popen(["venv\\Scripts\\python.exe", "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3) # Wait for it to start

# Make the request
token = app.create_token({'sub': 'Amir', 'role': 'admin'})
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/users',
    data=b'{"name":"Test","phone":"+998","username":"Test1234","password":"123"}',
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
)
try:
    resp = urllib.request.urlopen(req)
    print("Success:", resp.read())
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print("Body:", e.read().decode('utf-8'))

p.terminate()
p.wait()
print("STDOUT:", p.stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:", p.stderr.read().decode('utf-8', errors='ignore'))
