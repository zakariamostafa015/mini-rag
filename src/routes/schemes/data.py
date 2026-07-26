from pydantic import BaseModel
from typing import Optional
from models.enums.AssetTypeEnum import AssetTypeEnum

class ProcessRequest(BaseModel):
    file_id: str = None
    asset_type: AssetTypeEnum
    chunk_size: Optional[int] = 100
    overlap_size: Optional[int] = 20
    do_reset: Optional[int] = 0