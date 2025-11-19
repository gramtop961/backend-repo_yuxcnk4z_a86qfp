import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Chapter, QuizQuestion

app = FastAPI(title="Biology Learning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities to convert ObjectId for JSON responses

def to_str_id(doc: dict):
    if doc is None:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


@app.get("/")
def read_root():
    return {"message": "Biology Learning Backend is running"}


# --- Chapter Endpoints ---
class ChapterCreate(BaseModel):
    number: int
    title: str
    summary: str
    objectives: List[str] = []
    reference: Optional[str] = None
    sections: List[dict] = []


@app.post("/api/chapters", response_model=dict)
def create_chapter(payload: ChapterCreate):
    chapter = Chapter(**payload.model_dump())
    new_id = create_document("chapter", chapter)
    return {"id": new_id}


@app.get("/api/chapters", response_model=List[dict])
def list_chapters():
    docs = get_documents("chapter", {}, None)
    # sort by number ascending
    docs.sort(key=lambda x: x.get("number", 0))
    return [to_str_id(d) for d in docs]


@app.get("/api/chapters/{chapter_id}", response_model=dict)
def get_chapter(chapter_id: str):
    try:
        doc = db["chapter"].find_one({"_id": ObjectId(chapter_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid chapter id")
    if not doc:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return to_str_id(doc)


# --- Quiz Endpoints ---
class QuizCreate(BaseModel):
    chapter_id: str
    questions: List[QuizQuestion]


@app.post("/api/chapters/{chapter_id}/quizzes", response_model=dict)
def add_quiz_questions(chapter_id: str, payload: QuizCreate):
    if chapter_id != payload.chapter_id:
        raise HTTPException(status_code=400, detail="chapter_id mismatch")
    # verify chapter exists
    try:
        ch = db["chapter"].find_one({"_id": ObjectId(chapter_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid chapter id")
    if not ch:
        raise HTTPException(status_code=404, detail="Chapter not found")

    inserted_ids: List[str] = []
    for q in payload.questions:
        q_data = q.model_dump()
        new_id = create_document("quizquestion", q_data)
        inserted_ids.append(new_id)
    return {"inserted": len(inserted_ids), "ids": inserted_ids}


@app.get("/api/chapters/{chapter_id}/quizzes", response_model=List[dict])
def get_quiz_questions(chapter_id: str, limit: Optional[int] = 20):
    # default limit 20
    filter_dict = {"chapter_id": chapter_id}
    docs = get_documents("quizquestion", filter_dict, limit)
    return [to_str_id(d) for d in docs]


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
