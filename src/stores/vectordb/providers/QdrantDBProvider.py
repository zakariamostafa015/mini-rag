from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any
import logging

class QdrantDBProvider(VectorDBInterface):
    def __init__(self, dp_path: str, distance_method: str):

        self.client = None
        self.dp_path = dp_path
        self.distance_method = None

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT
        elif distance_method == DistanceMethodEnums.EUCLIDEAN.value:
            self.distance_method = models.Distance.EUCLIDEAN

        self.logger = logging.getLogger(__name__)

    def connect(self):
        # Qdrant client connects automatically on initialization
        self.client = QdrantClient(path=self.dp_path)

    def disconnect(self):
        # Qdrant client does not require explicit disconnection
        # raise NotImplementedError("Qdrant client does not require explicit disconnection.")
        return None

    def is_collection_exists(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    def list_all_collections(self) -> List:
        # collections = self.client.get_collections().collections
        # return [collection.name for collection in collections]
        return self.client.get_collections()
    
    def get_collection_info(self, collection_name: str) -> dict:
        # collection_info = self.client.get_collection(collection_name=collection_name)
        # return collection_info.dict()
        return self.client.get_collection(collection_name=collection_name)
    
    def delete_collection(self, collection_name: str):
        if self.is_collection_exists(collection_name):
            self.client.delete_collection(collection_name)

    def create_collection(self, collection_name: str,
                           embedding_size: int,
                           do_reset: bool = False):
        if do_reset:
            _ = self.delete_collection(collection_name)
        
        if not self.is_collection_exists(collection_name):
            _ =self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )
            return True
        
        return False

    def insert_one(self, collection_name: str, 
                   text: str,
                   vector: list,
                   metadata: dict = None,
                   record_id: str = None):

        if not self.is_collection_exists(collection_name):
            self.logger.error(f"Collection '{collection_name}' does not exist. Please create the collection first.")
            return False
        try:

            _ = self.client.upload_records(
                collection_name=collection_name,
                records=[
                    models.Record(
                        id=record_id,
                        vector=vector,
                        payload={
                            "text": text,
                            "metadata": metadata
                        }
                    )
                ]
            )
        except Exception as e:
            self.logger.error(f"Error inserting record into collection '{collection_name}': {e}")
            return False
        
        return True
    
    def insert_many(self, collection_name: str,
                    texts: list,
                    vectors: list,
                    metadatas: list = None,
                    record_ids: list = None,
                    batch_size: int = 50):

        if metadatas is None:
            metadatas = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(0, len(texts)))

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size
            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]
            batch_record_ids = record_ids[i:batch_end]

            batch_records = [
                models.Record(
                    id=batch_record_ids[x],
                    vector=batch_vectors[x],
                    payload={
                        "text": batch_texts[x],
                        "metadata": batch_metadatas[x]
                    }
                )
                for x in range(len(batch_texts))
            ]

            try:
                _ = self.client.upload_records(
                    collection_name=collection_name,
                    records=batch_records
                )
            except Exception as e:
                self.logger.error(f"Error inserting batch starting at index {i}: {e}")
                return False

        return True

    def search_by_vector(self, collection_name: str,
                         vector: list,
                         limit: int = 5):
        
        if not self.is_collection_exists(collection_name):
            self.logger.error(f"Collection '{collection_name}' does not exist. Please create the collection first.")
            return []

        try:
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=limit
            )
            return search_result
        except Exception as e:
            self.logger.error(f"Error searching in collection '{collection_name}': {e}")
            return []