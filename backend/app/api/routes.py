from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter()

# Document endpoints
@router.post("/documents/", response_model=schemas.Document)
def create_document(document: schemas.DocumentCreate, db: Session = Depends(get_db)):
    db_document = models.Document(**document.dict())
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

@router.get("/documents/", response_model=List[schemas.Document])
def get_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    documents = db.query(models.Document).offset(skip).limit(limit).all()
    return documents

@router.get("/documents/{document_id}", response_model=schemas.Document)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.put("/documents/{document_id}", response_model=schemas.Document)
def update_document(document_id: int, document: schemas.DocumentCreate, db: Session = Depends(get_db)):
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if db_document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    for key, value in document.dict().items():
        setattr(db_document, key, value)
    
    db.commit()
    db.refresh(db_document)
    return db_document

@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if db_document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.delete(db_document)
    db.commit()
    return {"message": "Document deleted"}

# Code endpoints
@router.post("/codes/", response_model=schemas.Code)
def create_code(code: schemas.CodeCreate, db: Session = Depends(get_db)):
    db_code = models.Code(**code.dict())
    db.add(db_code)
    db.commit()
    db.refresh(db_code)
    return db_code

@router.get("/codes/", response_model=List[schemas.Code])
def get_codes(document_id: int = None, db: Session = Depends(get_db)):
    query = db.query(models.Code)
    if document_id:
        query = query.filter(models.Code.document_id == document_id)
    codes = query.all()
    return codes

@router.delete("/codes/{code_id}")
def delete_code(code_id: int, db: Session = Depends(get_db)):
    db_code = db.query(models.Code).filter(models.Code.id == code_id).first()
    if db_code is None:
        raise HTTPException(status_code=404, detail="Code not found")
    
    db.delete(db_code)
    db.commit()
    return {"message": "Code deleted"}
