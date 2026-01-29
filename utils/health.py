from fastapi import FastAPI
import uvicorn
import asyncio
from config import Config

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Bot is alive"}

def run_health_check():
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)

if __name__ == "__main__":
    run_health_check()
