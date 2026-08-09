from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import logging

from controllers import NLPController
from .schemes.nlp import PushRequest, SearchRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.enums.ResponseEnums import ResponseSignal

logger = logging.getLogger('uvicorn.error')


nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"]
)


@nlp_router.post("/index/push/{project_id}")
async def index_project( request: Request, project_id: str, push_request: PushRequest):

    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    chunk_model = await ChunkModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.PROEJECT_NOT_FOUND_ERROR.value}
        )

    nlp_controller = NLPController(
        vector_client=request.app.state.vector_db_client,
        generation_client=request.app.state.llm_generation_client,
        embedding_client=request.app.state.llm_embedding_client,
        template_parser=request.app.state.template_parser
    )

    has_records =  True
    page_no = 1
    inserted_items_count = 0
    idx = 0

    while has_records:
        page_chunks = await chunk_model.get_chunks_by_project_id(
            project_id=project.id,
            page=page_no,
        )
        if len(page_chunks):
            page_no += 1

        if not page_chunks or len(page_chunks) == 0:
            has_records = False
            break

        chunk_ids = list(range(idx, idx + len(page_chunks)))
        idx += len(page_chunks)

        is_inserted = nlp_controller.index_info_vector_db(
            project=project,
            data_chunks=page_chunks,
            chunks_ids=chunk_ids,
            do_reset=push_request.do_reset
        )

        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"signal": ResponseSignal.INSERT_INTO_VECTOR_DB_FAILED.value}
            )
        inserted_items_count += len(page_chunks)

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"signal": ResponseSignal.INSERT_INTO_VECTOR_DB_SUCCESS.value,
                 "inserted_items_count": inserted_items_count}
    )



@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info( request: Request, project_id: str):

    project_model = await ProjectModel.create_instance(
            db_client=request.app.state.db_client
        )
    
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.PROEJECT_NOT_FOUND_ERROR.value}
        )

    nlp_controller = NLPController(
        vector_client=request.app.state.vector_db_client,
        generation_client=request.app.state.llm_generation_client,
        embedding_client=request.app.state.llm_embedding_client,
        template_parser=request.app.state.template_parser

    )

    collection_info = nlp_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"signal": ResponseSignal.VECTORDB_COLLECTION_INFO_RETRIVED.value,
                 "collection_info": collection_info}    
    )   
    

@nlp_router.post("/index/search/{project_id}")
async def search_project_index( request: Request, project_id: str, search_request: SearchRequest):
    project_model = await ProjectModel.create_instance(
                db_client=request.app.state.db_client
            )
        
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.PROEJECT_NOT_FOUND_ERROR.value}
        )

    nlp_controller = NLPController(
        vector_client=request.app.state.vector_db_client,
        generation_client=request.app.state.llm_generation_client,
        embedding_client=request.app.state.llm_embedding_client,
        template_parser=request.app.state.template_parser
    )

    search_results = nlp_controller.search_vector_db_collection(
        project=project,
        text=search_request.text,
        limit=search_request.limit
    )

    if not search_results:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": ResponseSignal.VECTORDB_SEARCH_FAILED.value}
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"signal": ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
                 "search_results": [result.dict() for result in search_results]}    
    )


@nlp_router.post("/index/answer/{project_id}")
async def search_project_index( request: Request, project_id: str, search_request: SearchRequest):
    project_model = await ProjectModel.create_instance(
                db_client=request.app.state.db_client
            )
        
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": ResponseSignal.PROEJECT_NOT_FOUND_ERROR.value}
        )

    nlp_controller = NLPController(
        vector_client=request.app.state.vector_db_client,
        generation_client=request.app.state.llm_generation_client,
        embedding_client=request.app.state.llm_embedding_client,
        template_parser=request.app.state.template_parser
    )

    answer, full_prompt, chat_history = nlp_controller.answer_rag_question(
        project=project,
        query=search_request.text,
        limit=search_request.limit
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.RAG_ANSWER_ERROR.value}
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.RAG_ANSWER_SUCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "chat_history": chat_history
        }
    )