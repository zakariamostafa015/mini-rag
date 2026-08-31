import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import text as sql_text

from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import (
    PgVectorDistanceMethodEnums,
    DistanceMethodEnums,
    PgVectorTableSchemeEnums,
    PgVectorIndexTypeEnum
)

from models.db_schemes import RetrieveDocument
from typing import List


class PGVectorProvider(VectorDBInterface):

    def __init__(
        self,
        db_client: async_sessionmaker[AsyncSession],
        default_vector_size: int = 786,
        distance_method: str = None,
        index_threshold: int = 100
    ):

        self.db_client = db_client
        self.default_vector_size = default_vector_size

        if distance_method == DistanceMethodEnums.COSINE.value:
            distance_method = PgVectorDistanceMethodEnums.COSINE.value
        elif distance_method == DistanceMethodEnums.DOT.value:
            distance_method = PgVectorDistanceMethodEnums.DOT.value


        self.distance_method = distance_method
        self.index_threshold = index_threshold

        self.pgvector_table_prefix = PgVectorTableSchemeEnums._PREFIX.value

        self.logger = logging.getLogger("uvicorn")

        self.default_index_name = (
            lambda collection_name: f"{collection_name}_vector_idx"
        )

    # =========================================================
    # CONNECTION
    # =========================================================

    async def connect(self):

        async with self.db_client() as session:

            async with session.begin():

                await session.execute(
                    sql_text(
                        "CREATE EXTENSION IF NOT EXISTS vector"
                    )
                )

    async def disconnect(self):
        pass

    # =========================================================
    # COLLECTION
    # =========================================================

    async def is_collection_exists(
        self,
        collection_name: str
    ) -> bool:

        async with self.db_client() as session:

            result = await session.execute(
                sql_text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_tables
                        WHERE tablename = :collection_name
                    )
                    """
                ),
                {
                    "collection_name": collection_name
                }
            )

            return bool(result.scalar())

    async def list_all_collections(self) -> List:

        async with self.db_client() as session:

            result = await session.execute(
                sql_text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE tablename LIKE :prefix
                    """
                ),
                {
                    "prefix": f"{self.pgvector_table_prefix}%"
                }
            )

            return result.scalars().all()

    async def get_collection_info(
        self,
        collection_name: str
    ) -> dict:

        exists = await self.is_collection_exists(
            collection_name
        )

        if not exists:
            return None

        async with self.db_client() as session:

            table_info_result = await session.execute(
                sql_text(
                    """
                    SELECT
                        schemaname,
                        tablename,
                        tableowner,
                        tablespace,
                        hasindexes
                    FROM pg_tables
                    WHERE tablename = :collection_name
                    """
                ),
                {
                    "collection_name": collection_name
                }
            )

            count_result = await session.execute(
                sql_text(
                    f"""
                    SELECT COUNT(*)
                    FROM {collection_name}
                    """
                )
            )

            table_data = table_info_result.mappings().first()

            if not table_data:
                return None

            return {
                "table_info": dict(table_data),
                "record_count": count_result.scalar()
            }

    async def delete_collection(
        self,
        collection_name: str
    ) -> bool:

        async with self.db_client() as session:

            async with session.begin():

                self.logger.info(
                    f"Deleting collection: {collection_name}"
                )

                delete_sql = sql_text(
                    f"""
                    DROP TABLE IF EXISTS {collection_name}
                    """
                )

                await session.execute(delete_sql)

        return True

    async def create_collection(
        self,
        collection_name: str,
        embedding_size: int,
        do_reset: bool = False
    ) -> bool:

        # -----------------------------------------
        # Reset existing collection
        # -----------------------------------------

        if do_reset:

            await self.delete_collection(
                collection_name=collection_name
            )

        # -----------------------------------------
        # Check if collection exists
        # -----------------------------------------

        is_collection_existed = (
            await self.is_collection_exists(
                collection_name=collection_name
            )
        )

        if is_collection_existed:
            return False

        self.logger.info(
            f"Creating collection: {collection_name}"
        )

        # -----------------------------------------
        # Create table
        # -----------------------------------------

        async with self.db_client() as session:

            async with session.begin():

                create_sql = sql_text(
                    f'CREATE TABLE {collection_name} ('
                        f'{PgVectorTableSchemeEnums.ID.value} bigserial PRIMARY KEY,'
                        f'{PgVectorTableSchemeEnums.TEXT.value} text, '
                        f'{PgVectorTableSchemeEnums.VECTOR.value} vector({embedding_size}), '
                        f'{PgVectorTableSchemeEnums.METADATA.value} jsonb DEFAULT \'{{}}\', '
                        f'{PgVectorTableSchemeEnums.CHUNK_ID.value} integer, '
                        f'FOREIGN KEY ({PgVectorTableSchemeEnums.CHUNK_ID.value}) REFERENCES chunks(chunk_id)'
                    ')'
                )

                await session.execute(create_sql)

        self.logger.info(
            f"Collection created successfully: {collection_name}"
        )

        return True

    # =========================================================
    # INDEX
    # =========================================================

    async def is_index_existed(
        self,
        collection_name: str
    ) -> bool:

        index_name = self.default_index_name(
            collection_name
        )

        async with self.db_client() as session:

            result = await session.execute(
                sql_text(
                    """
                    SELECT 1
                    FROM pg_indexes
                    WHERE tablename = :collection_name
                    AND indexname = :index_name
                    """
                ),
                {
                    "collection_name": collection_name,
                    "index_name": index_name
                }
            )

            return bool(
                result.scalar_one_or_none()
            )

    async def create_vector_index(
        self,
        collection_name: str,
        index_type: str = PgVectorIndexTypeEnum.HNSW.value
    ):

        # -----------------------------------------
        # Check index
        # -----------------------------------------

        is_index_existed = (
            await self.is_index_existed(
                collection_name
            )
        )

        if is_index_existed:
            return False

        # -----------------------------------------
        # Count records
        # -----------------------------------------

        async with self.db_client() as session:

            count_result = await session.execute(
                sql_text(
                    f"""
                    SELECT COUNT(*)
                    FROM {collection_name}
                    """
                )
            )

            record_count = count_result.scalar_one()

            if record_count < self.index_threshold:

                self.logger.info(
                    f"Skipping vector index for {collection_name}. "
                    f"Records: {record_count}, "
                    f"Threshold: {self.index_threshold}"
                )

                return False

            # -----------------------------------------
            # Create index
            # -----------------------------------------

            self.logger.info(
                f"START: Creating vector index for "
                f"collection: {collection_name}"
            )

            index_name = self.default_index_name(
                collection_name
            )

            create_idx_sql = sql_text(
                f"""
                CREATE INDEX {index_name}
                ON {collection_name}
                USING {index_type}
                (
                    {PgVectorTableSchemeEnums.VECTOR.value}
                    {self.distance_method}
                )
                """
            )

            await session.execute(create_idx_sql)

            self.logger.info(
                f"END: Created vector index for "
                f"collection: {collection_name}"
            )

        return True

    async def reset_vector_index(
        self,
        collection_name: str,
        index_type: str = PgVectorIndexTypeEnum.HNSW.value
    ):

        index_name = self.default_index_name(
            collection_name
        )

        async with self.db_client() as session:

            async with session.begin():

                drop_sql = sql_text(
                    f"""
                    DROP INDEX IF EXISTS {index_name}
                    """
                )

                await session.execute(drop_sql)

        return await self.create_vector_index(
            collection_name=collection_name,
            index_type=index_type
        )

    # =========================================================
    # INSERT ONE
    # =========================================================

    async def insert_one(
        self,
        collection_name: str,
        text: str,
        vector: list,
        metadata: dict = None,
        record_id: str = None
    ) -> bool:

        # -----------------------------------------
        # Check collection
        # -----------------------------------------

        is_collection_existed = (
            await self.is_collection_exists(
                collection_name
            )
        )

        if not is_collection_existed:

            self.logger.error(
                f"Cannot insert record. "
                f"Collection does not exist: {collection_name}"
            )

            return False

        # -----------------------------------------
        # Check record ID
        # -----------------------------------------

        if record_id is None:

            self.logger.error(
                "Cannot insert record. "
                "record_id is required."
            )

            return False

        # -----------------------------------------
        # Convert vector to pgvector format
        # -----------------------------------------

        vector_string = (
            "["
            + ",".join(str(v) for v in vector)
            + "]"
        )

        # -----------------------------------------
        # Metadata
        # -----------------------------------------

        metadata_json = json.dumps(
            metadata if metadata is not None else {},
            ensure_ascii=False
        )

        # -----------------------------------------
        # Insert
        # -----------------------------------------

        async with self.db_client() as session:

            async with session.begin():

                insert_sql = sql_text(
                    f"""
                    INSERT INTO {collection_name}
                    (
                        {PgVectorTableSchemeEnums.TEXT.value},
                        {PgVectorTableSchemeEnums.VECTOR.value},
                        {PgVectorTableSchemeEnums.METADATA.value},
                        {PgVectorTableSchemeEnums.CHUNK_ID.value}
                    )
                    VALUES
                    (
                        :text,
                        :vector,
                        :metadata,
                        :chunk_id
                    )
                    """
                )

                await session.execute(
                    insert_sql,
                    {
                        "text": text,
                        "vector": vector_string,
                        "metadata": metadata_json,
                        "chunk_id": record_id
                    }
                )

                await self.create_vector_index(
                            collection_name=collection_name
                        )
        return True

    # =========================================================
    # INSERT MANY
    # =========================================================

    async def insert_many(
        self,
        collection_name: str,
        texts: list,
        vectors: list,
        metadatas: list = None,
        record_ids: list = None,
        batch_size: int = 50
    ) -> bool:

        # -----------------------------------------
        # Check collection
        # -----------------------------------------

        is_collection_existed = (
            await self.is_collection_exists(
                collection_name
            )
        )

        if not is_collection_existed:

            self.logger.error(
                f"Cannot insert records. "
                f"Collection does not exist: {collection_name}"
            )

            return False

        # -----------------------------------------
        # Validate data
        # -----------------------------------------

        if not texts or not vectors:

            self.logger.error(
                "Texts and vectors cannot be empty."
            )

            return False

        if len(texts) != len(vectors):

            self.logger.error(
                "texts and vectors must have same length."
            )

            return False

        if record_ids is None:

            self.logger.error(
                "record_ids is required."
            )

            return False

        if len(record_ids) != len(texts):

            self.logger.error(
                "texts and record_ids must have same length."
            )

            return False

        # -----------------------------------------
        # Metadata
        # -----------------------------------------

        if metadatas is None:

            metadatas = [None] * len(texts)

        if len(metadatas) != len(texts):

            self.logger.error(
                "texts and metadatas must have same length."
            )

            return False

        # -----------------------------------------
        # Insert batches
        # -----------------------------------------

        try:

            async with self.db_client() as session:

                async with session.begin():

                    for i in range(
                        0,
                        len(texts),
                        batch_size
                    ):

                        batch_texts = texts[
                            i:i + batch_size
                        ]

                        batch_vectors = vectors[
                            i:i + batch_size
                        ]

                        batch_metadatas = metadatas[
                            i:i + batch_size
                        ]

                        batch_record_ids = record_ids[
                            i:i + batch_size
                        ]

                        values = []

                        for (
                            _text,
                            _vector,
                            _metadata,
                            _record_id
                        ) in zip(
                            batch_texts,
                            batch_vectors,
                            batch_metadatas,
                            batch_record_ids
                        ):

                            vector_string = (
                                "["
                                + ",".join(
                                    str(v)
                                    for v in _vector
                                )
                                + "]"
                            )

                            metadata_json = json.dumps(
                                _metadata
                                if _metadata is not None
                                else {},
                                ensure_ascii=False
                            )

                            values.append(
                                {
                                    "text": _text,
                                    "vector": vector_string,
                                    "metadata": metadata_json,
                                    "chunk_id": _record_id
                                }
                            )

                        batch_insert_sql = sql_text(
                            f"""
                            INSERT INTO {collection_name}
                            (
                                {PgVectorTableSchemeEnums.TEXT.value},
                                {PgVectorTableSchemeEnums.VECTOR.value},
                                {PgVectorTableSchemeEnums.METADATA.value},
                                {PgVectorTableSchemeEnums.CHUNK_ID.value}
                            )
                            VALUES
                            (
                                :text,
                                :vector,
                                :metadata,
                                :chunk_id
                            )
                            """
                        )

                        await session.execute(
                            batch_insert_sql,
                            values
                        )

            await self.create_vector_index(
                collection_name=collection_name
            )

            return True

        except Exception as e:

            self.logger.exception(
                f"Error while inserting records "
                f"into {collection_name}: {e}"
            )

            return False

    # =========================================================
    # SEARCH
    # =========================================================

    async def search_by_vector(
        self,
        collection_name: str,
        vector: list,
        limit: int = 5
    ):

        # -----------------------------------------
        # Check collection
        # -----------------------------------------

        is_collection_existed = (
            await self.is_collection_exists(
                collection_name
            )
        )

        if not is_collection_existed:

            self.logger.error(
                f"Cannot search. "
                f"Collection does not exist: {collection_name}"
            )

            return []

        # -----------------------------------------
        # Convert vector
        # -----------------------------------------

        vector_string = (
            "["
            + ",".join(
                str(v)
                for v in vector
            )
            + "]"
        )

        # -----------------------------------------
        # Search
        # -----------------------------------------

        async with self.db_client() as session:

            search_sql = sql_text(
                f"""
                SELECT
                    {PgVectorTableSchemeEnums.TEXT.value} AS text,

                    1 - (
                        {PgVectorTableSchemeEnums.VECTOR.value}
                        <=> :vector
                    ) AS score

                FROM {collection_name}

                ORDER BY score DESC

                LIMIT :limit
                """
            )

            result = await session.execute(
                search_sql,
                {
                    "vector": vector_string,
                    "limit": limit
                }
            )

            records = result.fetchall()

            return [
                RetrieveDocument(
                    text=record.text,
                    score=record.score
                )
                for record in records
            ]
