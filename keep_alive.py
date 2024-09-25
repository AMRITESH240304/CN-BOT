from fastapi import FastAPI
import uvicorn
from threading import Thread

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Coding Ninjas SRM"}

def run():
    uvicorn.run(app, host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()