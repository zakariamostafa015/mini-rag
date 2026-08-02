from fastapi import FastAPI
from routes import base, data
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import Settings, get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
app = FastAPI()

async def startup_span():
    settings = get_settings()
    app.state.settings = settings
    app.state.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URI)
    app.state.mongodb_db = app.state.mongodb_conn[settings.MONGODB_DB_NAME]

    llm_provider_factory = LLMProviderFactory(config=settings)
    vector_db_provider_factory = VectorDBProviderFactory(config=settings)

    # generation client
    app.state.llm_generation_client = llm_provider_factory.create(provider=settings.LLM_GENERATION_PROVIDER)
    app.state.llm_generation_client.set_generation_model(model_id= settings.LLM_GENERATION_MODEL_ID)

    # embedding client
    app.state.llm_embedding_client = llm_provider_factory.create(provider=settings.LLM_EMBEDDING_PROVIDER)
    app.state.llm_embedding_client.set_embedding_model(model_id= settings.LLM_EMBEDDING_MODEL_ID,
                                                        emembedding_size= settings.LLM_EMBEDDING_MODEL_SIZE)

    # vector db client
    app.state.vector_db_client = vector_db_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    app.state.vector_db_client.connect()

async def shutdown_span():
    app.state.mongodb_conn.close()
    app.state.vector_db_client.disconnect()

app.router.lifespan.on_startup.append(startup_span)
app.router.lifespan.on_shutdown.append(shutdown_span)

app.include_router(base.base_router)
app.include_router(data.data_router)