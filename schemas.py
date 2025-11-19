"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# --- Domain Schemas for Biology Learning App ---

class Chapter(BaseModel):
    """
    Chapters of the biology course.
    Collection name: "chapter"
    """
    number: int = Field(..., ge=1, description="Chapter number")
    title: str = Field(..., description="Chapter title")
    summary: str = Field(..., description="Ringkasan materi dengan kata-kata sendiri (bukan kutipan langsung buku)")
    objectives: List[str] = Field(default_factory=list, description="Tujuan pembelajaran per bab")
    reference: Optional[str] = Field(None, description="Referensi belajar, misal: 'Campbell Biology ed.11, Bab 1' (tanpa kutipan teks)")
    sections: List[dict] = Field(default_factory=list, description="Daftar bagian: [{'title': str, 'content': str}]")

class QuizQuestion(BaseModel):
    """
    Multiple-choice questions for each chapter.
    Collection name: "quizquestion"
    """
    chapter_id: str = Field(..., description="ID bab terkait")
    question: str = Field(..., description="Teks soal (pilihan ganda)")
    options: List[str] = Field(..., min_items=2, description="Pilihan jawaban")
    correct_index: int = Field(..., ge=0, description="Index jawaban benar di options")
    explanation: str = Field(..., description="Penjelasan mengapa jawaban benar")
    difficulty: str = Field("OSN-N", description="Level kesulitan, default OSN-N")

# Legacy examples kept for reference (not used by app)
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
