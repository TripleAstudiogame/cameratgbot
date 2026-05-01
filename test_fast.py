from fastapi import FastAPI
import threading
import uvicorn
import time
import urllib.request

app = FastAPI()

@app.get('/')
def index():
    raise Exception('test')

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8007, log_level="error")

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)

try:
    resp = urllib.request.urlopen('http://127.0.0.1:8007/')
    print("Status:", resp.status_code)
except Exception as e:
    print(e)
    if hasattr(e, 'read'):
        print("Body:", e.read().decode('utf-8'))
