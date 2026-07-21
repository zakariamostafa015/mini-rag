from fastapi import FastAPI
from routes import base, data
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import Settings, get_settings

app = FastAPI()

@app.on_event("startup")
async def startup_db_client():
    settings = get_settings()
    app.state.settings = settings
    app.state.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URI)
    app.state.mongodb_db = app.state.mongodb_conn[settings.MONGODB_DB_NAME]

@app.on_event("shutdown")
async def shutdown_db_client():
    app.state.mongodb_conn.close()

app.include_router(base.base_router)
app.include_router(data.data_router)