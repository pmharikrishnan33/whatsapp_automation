from fastapi import FastAPI
from app.routes.webhook import router as webhook_router

app=FastAPI()
app.include_router(webhook_router)

@app.get('/')
def home():
    return {"Zyphor Technologies"}