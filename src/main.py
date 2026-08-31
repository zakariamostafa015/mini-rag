from fastapi import FastAPI
from routes import base, data, nlp
# from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import Settings, get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

app = FastAPI()

async def startup_span():
    settings = get_settings()
    app.state.settings = settings

    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.state.db_engine = create_async_engine(postgres_conn)

    app.state.db_client = sessionmaker(
        app.state.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # fro MongoDb connection if we will use again
    # app.state.mongodb_conn = AsyncIOMotorClient(settings.MONGODB_URI)
    # app.state.db_client = app.state.mongodb_conn[settings.MONGODB_DB_NAME]

    llm_provider_factory = LLMProviderFactory(config=settings)
    vector_db_provider_factory = VectorDBProviderFactory(config=settings, db_client=app.state.db_client)

    # generation client
    app.state.llm_generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.state.llm_generation_client.set_generation_model(model_id= settings.GENERATION_MODEL_ID)

    # embedding client
    app.state.llm_embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.state.llm_embedding_client.set_embedding_model(model_id= settings.EMBEDDING_MODEL_ID,
                                                        embedding_size= settings.EMBEDDING_MODEL_SIZE)

    # vector db client
    app.state.vector_db_client = vector_db_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await app.state.vector_db_client.connect()

    app.state.template_parser = TemplateParser(
        language=settings.PRIMARY_LANGUAGE,
        default_language=settings.DEFAULT_LANGUAGE
    )

async def shutdown_span():
    # app.state.mongodb_conn.close()
    app.state.db_engine.dispose()
    await app.state.vector_db_client.disconnect()

# app.router.lifespan.on_startup.append(startup_span)
# app.router.lifespan.on_shutdown.append(shutdown_span)

app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)