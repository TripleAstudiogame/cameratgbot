import urllib.request
import urllib.error
import json
import app

token = app.create_token({'sub':'admin', 'role':'admin'})

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/users', 
    data=b'{"name":"Amir","phone":"+998","username":"Amir123","password":"123"}', 
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
)
try:
    urllib.request.urlopen(req)
    print("Success")
except urllib.error.HTTPError as e:
    print(e.read())
