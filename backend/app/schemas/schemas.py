from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CodeBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#3b82f6"
    selected_text: str

class CodeCreate(CodeBase):
    document_id: int

class Code(CodeBase):
    id: int
    document_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    title: str
    content: str

class DocumentCreate(DocumentBase):
    pass

class Document(DocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    codes: List[Code] = []
    
    class Config:
        from_attributes = True


class PromptBase(BaseModel):
    display_name: str
    prompt: str
    type: str


class PromptCreate(PromptBase):
    uuid: str


class Prompt(PromptBase):
    rowid: int
    uuid: str

    class Config:
        from_attributes = True
