from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson import ObjectId  #came with motor

class Project(BaseModel):
    _id: Optional[ObjectId] = None
    project_id: str = Field(..., min_length=1)

    @field_validator("project_id")
    def validate_project_id(cls, value):
        if not value.isalpha() or len(value) < 1:
            raise ValueError("project_id must be a non-empty string containing only alphabetic characters.")
        return value
    

    class Config:
        arbitrary_types_allowed = True