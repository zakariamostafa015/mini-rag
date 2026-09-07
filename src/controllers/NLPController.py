from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List

import json
class NLPController(BaseController):

    def __init__(self, vector_client, generation_client, embedding_client, template_parser):
        super().__init__()
        self.vector_client = vector_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser


    def create_collection_name(self, project_id: str):
        return f"collection_{self.vector_client.default_vector_size}_{project_id}".strip()

    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id = project.project_id)
        return await self.vector_client.delete_collection(collection_name= collection_name)

    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id = project.project_id)
        collection_info = await self.vector_client.get_collection_info(collection_name= collection_name)
        collection_info = json.loads(
            json.dumps(collection_info, default=lambda o: o.__dict__)  # Convert to JSON string and then back to dict
        )

        return collection_info

    async def index_info_vector_db(self, project: Project, 
                             data_chunks: List[DataChunk],
                             chunks_ids: List[int],
                             do_reset: bool = False):

        # step 1: get collection name
        collection_name = self.create_collection_name(project_id = project.project_id)

        # step 2: manage items
        texts = [chunk.chunk_text for chunk in data_chunks]
        metadatas = [chunk.chunk_metadata for chunk in data_chunks]
        vectors = self.embedding_client.embed_text(text=texts, document_type=DocumentTypeEnum.DOCUMENT)

        # step 3: create collection if not exists
        _ = await self.vector_client.create_collection(
                    collection_name=collection_name,
                    embedding_size=self.embedding_client.embedding_size,
                    do_reset=do_reset
        )
        # step 4: insert items into vector db        
        _ = await self.vector_client.insert_many(
                    collection_name=collection_name,
                    texts = texts,
                    vectors = vectors,
                    metadatas = metadatas,
                    record_ids = chunks_ids
                )

        return True

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 5):
        # step 1: get collection name
        query_vector = None
        collection_name = self.create_collection_name(project_id = project.project_id)

        # step 2: embed the text
        vectors = self.embedding_client.embed_text(
            text=text, 
            document_type=DocumentTypeEnum.QUERY
        )

        if not vectors or len(vectors) == 0:
            self.logger.error("Error while embedding the text for search")
            return False

        if isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]

        if not query_vector:
            return False
        
        # step 3: search in vector db
        search_results = await self.vector_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        if not search_results or len(search_results) == 0:
            self.logger.error("Error while searching in vector db")
            return False
        
        return search_results

    async def answer_rag_question(self, project: Project, query: str, limit: int = 5):

        answer, full_prompt, chat_history = None, None, None

        # step 1: search in vector db
        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            self.logger.error("Error while searching in vector db")
            return answer, full_prompt, chat_history
        
        # step 2: generate answer using llm generation client
        system_prompt = self.template_parser.get("rag","system_prompt")

        # document_prompts = []
        # for idx, doc in enumerate(retrieved_documents):
        #     document_prompts.append(
        #         self.template_parser.get("rag","document_prompt", {
        #             "doc_num": idx +1,
        #             "chunk_text": doc.text
        #         })
        #     )

        document_prompts = "\n".join([
            self.template_parser.get("rag","document_prompt", {
                "doc_num": idx +1,
                "chunk_text": self.generation_client.process_text(doc.text)
            })
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get("rag","footer_prompt", { 
            "query": query 
        })

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt, 
                role=self.generation_client.enums.SYSTEM.value
            )
        ]

        full_prompt = "\n\n".join([
            document_prompts, footer_prompt
        ])

        answer = self.generation_client.generate_text(
            prompt= full_prompt,
            chat_history = chat_history
        )

        return answer, full_prompt, chat_history