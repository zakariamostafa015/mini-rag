from .BaseDataModel import BaseDataModel
from .db_schemes.project import Project
from .enums.DataBaseEnum import DataBaseEnum
from typing import Optional
from bson import ObjectId

class ProjectModel(BaseDataModel):
    
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECTS_NAME.value]

    async def create_project(self, project: Project):
        result = await self.collection.insert_one(project.dict(by_alias=True, exclude_unset=True))  # use by_alias=True to ensure the _id field is correctly handled
        project._id = result.inserted_id

        return project

    async def get_project_or_create_one(self, project_id: str):
        record = await self.collection.find_one({
            "project_id": project_id
        })

        if record is None:
            new_project = Project(project_id=project_id)
            new_project = await self.create_project(project=new_project)

            return new_project
        else:
            return Project(**record)


    async def get_all_projects(self, page: int = 1, page_size: int = 10):

        # count total number of documents in the collection
        total_count = await self.collection.count_documents({})

        # calculate the number of pages
        total_pages = (total_count + page_size - 1) // page_size
        if total_count % page_size > 0:
            total_pages += 1

        skip = (page - 1) * page_size
        cursor = self.collection.find().skip(skip).limit(page_size)

        projects = []
        async for proj in cursor:
            projects.append(Project(**proj))

        return projects, total_pages
    
'''
    async def get_all_projects(self, page: int = 1, page_size: int = 10):
        skip = (page - 1) * page_size
        cursor = self.collection.find().skip(skip).limit(page_size)
        projects = await cursor.to_list(length=page_size)

        return [Project(**proj) for proj in projects]

'''