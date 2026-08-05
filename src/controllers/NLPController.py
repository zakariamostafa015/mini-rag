from .BaseController import BaseController
from models.db_schemes import Project, DataChunk, project
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
        return f"collection_{project_id}".strip()

    def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id = project.project_id)
        return self.vector_client.delete_collection(collection_name= collection_name)

    def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id = project.project_id)
        collection_info = self.vector_client.get_collection_info(collection_name= collection_name)
        collection_info = json.loads(
            json.dumps(collection_info, default=lambda o: o.__dict__)  # Convert to JSON string and then back to dict
        )

        return collection_info

    def index_info_vector_db(self, project: Project, 
                             data_chunks: List[DataChunk],
                             chunks_ids: List[int],
                             do_reset: bool = False):

        # step 1: get collection name
        collection_name = self.create_collection_name(project_id = project.project_id)

        # step 2: manage items
        texts = [chunk.chunk_text for chunk in data_chunks]
        metadatas = [chunk.chunk_metadata for chunk in data_chunks]
        vectors = [
            self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnum.DOCUMENT)
            for text in texts
        ]

        # step 3: create collection if not exists
        _ = self.vector_client.create_collection(
                    collection_name=collection_name,
                    embedding_size=self.embedding_client.embedding_size,
                    do_reset=do_reset
        )
        # step 4: insert items into vector db        
        _ = self.vector_client.insert_many(
                    collection_name=collection_name,
                    texts = texts,
                    vectors = vectors,
                    metadatas = metadatas,
                    record_ids = chunks_ids
                )

        return True

    def search_vector_db_collection(self, project: Project, text: str, limit: int = 5):
        # step 1: get collection name
        collection_name = self.create_collection_name(project_id = project.project_id)

        # step 2: embed the text
        vector = self.embedding_client.embed_text(
            text=text, 
            document_type=DocumentTypeEnum.QUERY
        )

        if not vector or len(vector) == 0:
            self.logger.error("Error while embedding the text for search")
            return False
        
        # step 3: search in vector db
        search_results = self.vector_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit
        )

        if not search_results or len(search_results) == 0:
            self.logger.error("Error while searching in vector db")
            return False
        
        return search_results

    def answer_rag_question(self, project: Project, query: str, limit: int = 5):

        answer, full_prompt, chat_history = None, None, None

        # step 1: search in vector db
        retrieved_documents = self.search_vector_db_collection(
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
                "chunk_text": doc.text
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