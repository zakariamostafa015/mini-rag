from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk
from .enums.DataBaseEnum import DataBaseEnum
from bson import ObjectId  #came with motor
from sqlalchemy.future import select
from sqlalchemy import func, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

class ChunkModel(BaseDataModel):
    def __init__(self,  db_client: async_sessionmaker[AsyncSession]):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls,  db_client: async_sessionmaker[AsyncSession]):
        instance = cls(db_client)
        return instance


    async def create_chunk(self, chunk: DataChunk):
        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
            await session.commit()
            await session.refresh(chunk)

        return chunk

    async def get_chunk_by_id(self, chunk_id: str):
        async with self.db_client() as session:
            result = await session.execute(select(DataChunk).where(
                DataChunk.chunk_id == chunk_id
            ))
            chunk = result.scalar_one_or_none()
        return chunk

    async def get_chunks_by_project_id(self, project_id: ObjectId, page: int = 1, page_size: int = 50):
        skip = (page - 1) * page_size
        limit = page_size
        async with self.db_client() as session:
            stmt = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset(skip).limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()
        return records
    
    async def insert_many_chunks(self, chunks: list, batch_size: int = 100):
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    session.add_all(batch)
            await session.commit()
        return len(chunks)

    async def delete_chunk_by_project_id(self, project_id: int):
        async with self.db_client() as session:
            stmt = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(stmt)
            await session.commit()
        return result.rowcount