from fastapi import FastAPI
from routes import base, data
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import Settings, get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory

app = FastAPI()

async def startup_db_client():
    settings = get_settings()
    app.state.settings = settings
    app.state.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URI)
    app.state.mongodb_db = app.state.mongodb_conn[settings.MONGODB_DB_NAME]

    llm_provider_factory = LLMProviderFactory(config=settings)

    # generation client
    app.state.llm_generation_client = llm_provider_factory.create(provider=settings.LLM_GENERATION_PROVIDER)
    app.state.llm_generation_client.set_generation_model(model_id= settings.LLM_GENERATION_MODEL_ID)

    # embedding client
    app.state.llm_embedding_client = llm_provider_factory.create(provider=settings.LLM_EMBEDDING_PROVIDER)
    app.state.llm_embedding_client.set_embedding_model(model_id= settings.LLM_EMBEDDING_MODEL_ID,
                                                        emembedding_size= settings.LLM_EMBEDDING_MODEL_SIZE)

async def shutdown_db_client():
    app.state.mongodb_conn.close()

app.router.lifespan.on_startup.append(startup_db_client)
app.router.lifespan.on_shutdown.append(shutdown_db_client)

app.include_router(base.base_router)
app.include_router(data.data_router)