import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.analysis.analyze import analyze_chunks
from app.analysis.compare import compare_chunks
from app.database.db import get_session
from app.database.models import StoredChunk, StoredDocument
from app.document_processing.chunk import chunk_document
from app.document_processing.extract import extract_document
from app.document_processing.models import Chunk
from app.rag.answer import answer_question
from app.schemas import QuestionRequest
from app.config import get_settings
from app.api.security import current_user

router = APIRouter()


def _chunks(document: StoredDocument) -> list[Chunk]:
    return [Chunk(document.id, document.name, c.page, c.section, c.clause, c.text) for c in document.chunks]


def _get(document_id: str, db: Session, owner_id: str) -> StoredDocument:
    doc = db.query(StoredDocument).filter_by(id=document_id, owner_id=owner_id).first()
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_session), owner_id: str = Depends(current_user)):
    name = file.filename or "document"
    content = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(content) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Maximum upload size is {get_settings().max_upload_mb} MB.")
    try:
        extracted = extract_document(name, content)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    doc_id = str(uuid.uuid4())
    doc = StoredDocument(id=doc_id, name=name, owner_id=owner_id, content_hash=hashlib.sha256(content).hexdigest())
    doc.chunks = [StoredChunk(page=c.page, section=c.section, clause=c.clause, text=c.text) for c in chunk_document(doc_id, extracted)]
    db.add(doc)
    db.commit()
    return {"id": doc.id, "name": doc.name, "pages": len(extracted.pages), "chunks": len(doc.chunks), "metadata": extracted.metadata}


@router.get("/documents")
def list_documents(db: Session = Depends(get_session), owner_id: str = Depends(current_user)):
    docs = db.query(StoredDocument).filter_by(owner_id=owner_id).order_by(StoredDocument.created_at.desc()).all()
    return [{"id": d.id, "name": d.name, "created_at": d.created_at.isoformat()} for d in docs]


@router.get("/documents/{document_id}")
def document_analysis(document_id: str, db: Session = Depends(get_session), owner_id: str = Depends(current_user)):
    doc = _get(document_id, db, owner_id)
    return {"id": doc.id, "name": doc.name, "analysis": analyze_chunks(_chunks(doc))}


@router.post("/documents/{document_id}/ask")
def ask_document(document_id: str, request: QuestionRequest, db: Session = Depends(get_session), owner_id: str = Depends(current_user)):
    doc = _get(document_id, db, owner_id)
    history = [turn.model_dump() for turn in request.history]
    return answer_question(request.question, _chunks(doc), history)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_session), owner_id: str = Depends(current_user)):
    doc = _get(document_id, db, owner_id)
    db.delete(doc)
    db.commit()


@router.post("/compare")
async def compare_documents(file_a: UploadFile = File(...), file_b: UploadFile = File(...), owner_id: str = Depends(current_user)):
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    extracted = []
    for file in (file_a, file_b):
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(413, f"Maximum upload size is {get_settings().max_upload_mb} MB per file.")
        try:
            doc = extract_document(file.filename or "document", content)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        doc_id = str(uuid.uuid4())
        extracted.append(chunk_document(doc_id, doc))
    return {"changes": compare_chunks(*extracted), "notice": "Detected text differences only; no judgment of legal effect."}
