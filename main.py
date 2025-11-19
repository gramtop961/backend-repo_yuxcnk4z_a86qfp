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


# --- Seed Endpoint for Sample Content ---
@app.post("/api/seed/sample", response_model=dict)
def seed_sample():
    """
    Seed a sample chapter (Bab 1) with 20 OSN-N level questions.
    Safe to call multiple times: it won't duplicate chapter and will only fill up to 20 questions.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # Check existing chapter by number
    chapter_doc = db["chapter"].find_one({"number": 1})
    if chapter_doc:
        chapter_id = str(chapter_doc["_id"])
    else:
        ch_payload = Chapter(
            number=1,
            title="Tema Besar Biologi & Penyelidikan Ilmiah",
            summary=(
                "Biologi mempelajari kehidupan dari skala molekul hingga biosfer. Pola umum yang menyatukan bidang ini meliputi organisasi berjenjang, "
                "hubungan struktur–fungsi, aliran energi dan daur materi, regulasi melalui umpan balik, informasi genetik, evolusi sebagai penjelas keberagaman, "
                "serta metode ilmiah sebagai cara mendapatkan pengetahuan yang bisa diuji. Ringkasan ini merangkum kerangka berpikir untuk memahami fenomena hayati "
                "dan cara ilmuwan merumuskan pertanyaan, hipotesis, eksperimen, hingga penarikan kesimpulan yang dapat direplikasi."
            ),
            objectives=[
                "Menjelaskan hierarki organisasi kehidupan dari molekul hingga biosfer",
                "Membedakan hipotesis dan teori ilmiah serta peran prediksi",
                "Menguraikan aliran energi dan daur materi dalam sistem biologis",
                "Menjelaskan mekanisme umpan balik negatif dan positif",
                "Menunjukkan bagaimana evolusi menyatukan dan menjelaskan keanekaragaman hayati"
            ],
            reference="Campbell Biology ed.11, Bab pengantar (rujukan konsep, tanpa kutipan teks)",
            sections=[
                {"title": "Hierarki Organisasi", "content": "Tingkat organisasi: molekul → organel → sel → jaringan → organ → sistem organ → organisme → populasi → komunitas → ekosistem → biosfer."},
                {"title": "Struktur–Fungsi", "content": "Bentuk suatu struktur biologis membatasi dan memungkinkan fungsinya, dari lipatan protein hingga bentuk paruh burung."},
                {"title": "Energi & Materi", "content": "Energi mengalir (umumnya dari cahaya → kimia → panas), materi berdaur melalui interaksi biotik–abiotik."},
                {"title": "Informasi Genetik", "content": "DNA menyimpan informasi; ekspresi gen menghubungkan genotipe dan fenotipe; regulasi mengatur waktu/tempat ekspresi."},
                {"title": "Regulasi & Homeostasis", "content": "Umpan balik negatif menstabilkan, umpan balik positif memperkuat perubahan hingga tercapai peristiwa spesifik."},
                {"title": "Metode Ilmiah", "content": "Observasi → pertanyaan → hipotesis → prediksi → uji/eksperimen → analisis → kesimpulan → replikasi/peer review."},
                {"title": "Evolusi", "content": "Seleksi alam menjelaskan adaptasi; hubungan kekerabatan direkonstruksi melalui bukti komparatif dan molekuler."}
            ]
        )
        chapter_id = create_document("chapter", ch_payload)
        chapter_doc = db["chapter"].find_one({"_id": ObjectId(chapter_id)})

    # Count existing questions
    existing_q = db["quizquestion"].count_documents({"chapter_id": str(chapter_doc["_id"])})

    # Build up to 20 questions
    questions: List[dict] = []

    if existing_q < 20:
        cid = str(chapter_doc["_id"]) 
        questions = [
            {
                "chapter_id": cid,
                "question": "Manakah urutan hierarki organisasi kehidupan yang tepat dari kecil ke besar?",
                "options": [
                    "Organel → sel → jaringan → organ → organisme",
                    "Molekul → organel → sel → jaringan → organ",
                    "Sel → molekul → organel → jaringan → organ",
                    "Molekul → sel → organel → jaringan → organ"
                ],
                "correct_index": 1,
                "explanation": "Urutan benar: molekul → organel → sel → jaringan → organ (kemudian sistem organ → organisme → populasi → komunitas → ekosistem → biosfer).",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Dalam sistem biologis, energi umumnya masuk sebagai … dan keluar sebagai …",
                "options": [
                    "Bahan kimia; kalor",
                    "Cahaya; kalor",
                    "Kalor; cahaya",
                    "Elektron; proton"
                ],
                "correct_index": 1,
                "explanation": "Energi masuk terutama sebagai cahaya (pada ekosistem) dan diubah ke energi kimia; pada akhirnya hilang sebagai kalor.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pernyataan yang tepat tentang hipotesis dan teori ilmiah adalah …",
                "options": [
                    "Teori adalah dugaan awal, hipotesis adalah hukum alam",
                    "Hipotesis adalah penjelasan sementara yang dapat diuji; teori adalah kerangka penjelas luas dengan dukungan bukti kuat",
                    "Teori tidak dapat direvisi sementara hipotesis dapat",
                    "Hipotesis dan teori setara dan saling menggantikan"
                ],
                "correct_index": 1,
                "explanation": "Hipotesis: pernyataan penjelas sementara yang dapat diuji melalui prediksi. Teori: sintesis penjelasan luas, konsisten, banyak bukti, tetap dapat direvisi.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Contoh umpan balik negatif dalam fisiologi adalah …",
                "options": [
                    "Kontraksi uterus yang dipicu oksitosin saat persalinan",
                    "Pembekuan darah yang semakin cepat saat cedera",
                    "Pengaturan gula darah oleh insulin–glukagon",
                    "Letupan potensial aksi pada neuron"
                ],
                "correct_index": 2,
                "explanation": "Insulin menurunkan glukosa ketika tinggi; glukagon menaikkan saat rendah → menuju kestabilan (homeostasis), ciri umpan balik negatif.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Manakah pasangan struktur–fungsi yang PALING tepat?",
                "options": [
                    "Dinding sel tumbuhan tipis → mencegah tekanan turgor",
                    "Mikrovili usus memperkecil luas permukaan untuk memperlambat absorbsi",
                    "Lipatan membran mitokondria (krista) memperluas area untuk reaksi respirasi",
                    "Hemoglobin berbentuk bola halus agar tidak mengikat O2"
                ],
                "correct_index": 2,
                "explanation": "Krista memperbesar luas permukaan membran dalam mitokondria, meningkatkan kapasitas rantai transpor elektron dan kemiosmosis.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pernyataan yang BENAR tentang informasi genetik adalah …",
                "options": [
                    "DNA adalah satu-satunya molekul informasi di semua makhluk hidup",
                    "Urutan nukleotida pada DNA menyandi urutan asam amino protein",
                    "Semua gen selalu diekspresikan pada setiap sel suatu organisme",
                    "RNA tidak berperan dalam penerjemahan informasi"
                ],
                "correct_index": 1,
                "explanation": "Kodon pada mRNA berasal dari transkripsi DNA dan menentukan urutan asam amino; ekspresi gen diatur ruang–waktu; beberapa virus ber-RNA.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Argumen inti evolusi yang menjelaskan adaptasi adalah …",
                "options": [
                    "Kebutuhan organisme memicu perubahan genetik terarah",
                    "Seleksi alam bertindak atas variasi yang sudah ada sehingga frekuensi alel berubah",
                    "Mutasi selalu menguntungkan sehingga terseleksi",
                    "Evolusi terjadi demi kesempurnaan individu"
                ],
                "correct_index": 1,
                "explanation": "Seleksi alam bekerja pada variasi fenotip/genetik yang telah ada; lingkungan menyaring kombinasi yang meningkatkan keberhasilan reproduktif.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Dalam eksperimen, fungsi kontrol negatif adalah …",
                "options": [
                    "Membuat variabel bebas lebih kuat",
                    "Menunjukkan hasil yang diharapkan bila perlakuan efektif",
                    "Menunjukkan hasil dasar bila tidak ada perlakuan, untuk pembanding",
                    "Menggandakan ukuran sampel"
                ],
                "correct_index": 2,
                "explanation": "Kontrol negatif tidak menerima perlakuan sehingga mengungkap nilai dasar/artefak; kontrol positif menerima perlakuan yang pasti memberi efek.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Variabel yang harus dikendalikan (controlled variables) adalah …",
                "options": [
                    "Variabel bebas yang dimanipulasi",
                    "Variabel respon yang diukur",
                    "Faktor lain yang dapat memengaruhi respon dan harus dijaga konstan",
                    "Variabel yang tidak dapat diukur"
                ],
                "correct_index": 2,
                "explanation": "Variabel terkendali dijaga sama di semua kelompok agar perubahan pada variabel terikat dapat diatribusikan ke variabel bebas.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Manakah pernyataan yang PALING sesuai tentang aliran energi dan daur materi?",
                "options": [
                    "Energi dan materi sama-sama berdaur",
                    "Energi berdaur, materi mengalir",
                    "Energi mengalir satu arah, materi berdaur",
                    "Keduanya mengalir satu arah"
                ],
                "correct_index": 2,
                "explanation": "Energi masuk terutama sebagai cahaya dan berakhir sebagai kalor (tidak berdaur), sedangkan atom unsur berpindah antar kompartemen dan berdaur.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pernyataan benar tentang pendekatan reduksionisme dan sistem adalah …",
                "options": [
                    "Reduksionisme tidak berguna dalam biologi modern",
                    "Pendekatan sistem menolak data molekuler",
                    "Reduksionisme memecah sistem menjadi bagian; biologi sistem memetakan interaksi bagian-bagian",
                    "Keduanya identik"
                ],
                "correct_index": 2,
                "explanation": "Reduksionisme mengurai komponen untuk memahami mekanisme; biologi sistem mensintesis kembali interaksi untuk memodelkan perilaku emergen.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Sebuah hipotesis dinyatakan kuat jika …",
                "options": [
                    "Mampu menjelaskan semua fenomena alam",
                    "Spesifik, menghasilkan prediksi teruji, dan falsifiabel",
                    "Didukung oleh satu percobaan yang berhasil",
                    "Tidak dapat dibantah"
                ],
                "correct_index": 1,
                "explanation": "Hipotesis harus dapat menghasilkan prediksi yang bisa salah bila bertentangan dengan data (falsifiabel) dan cukup spesifik untuk diuji.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Contoh terbaik umpan balik positif adalah …",
                "options": [
                    "Termoregulasi melalui keringat",
                    "Pembekuan darah mempercepat aktivasi faktor pembeku",
                    "Pengaturan pH darah oleh sistem penyangga",
                    "Pengendalian glukosa darah oleh insulin"
                ],
                "correct_index": 1,
                "explanation": "Dalam koagulasi, produk antara mengaktifkan lebih banyak faktor berikutnya → amplifikasi hingga bekuan terbentuk (batas proses jelas).",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Manakah yang BUKAN bukti kuat bagi evolusi?",
                "options": [
                    "Fosil transisi",
                    "Homologi struktur dan molekuler",
                    "Variasi acak hasil sampling kecil",
                    "Distribusi biogeografis konsisten"
                ],
                "correct_index": 2,
                "explanation": "Variasi acak pada sampel kecil (drift) adalah mekanisme mikro, bukan bukti komparatif makro seperti fosil, homologi, dan biogeografi.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Dalam rancangan eksperimen, replikasi diperlukan untuk …",
                "options": [
                    "Menggantikan kontrol",
                    "Mengurangi pengaruh kebetulan dan memperkirakan variabilitas",
                    "Memperbanyak variabel",
                    "Mendapatkan nilai p = 0"
                ],
                "correct_index": 1,
                "explanation": "Replikasi memungkinkan estimasi varians dan meningkatkan daya statistik, bukan untuk menjamin hasil tertentu atau mengganti kontrol.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pernyataan yang tepat tentang pohon filogenetik …",
                "options": [
                    "Selalu menunjukkan urutan kronologis kemunculan spesies",
                    "Merepresentasikan hipotesis hubungan kekerabatan berdasarkan bukti",
                    "Menunjukkan tingkat kemajuan suatu spesies",
                    "Tidak dapat berubah ketika data baru muncul"
                ],
                "correct_index": 1,
                "explanation": "Pohon filogenetik adalah hipotesis yang dapat direvisi; tidak menyiratkan kemajuan linear, melainkan kekerabatan berdasarkan data morfologi/molekuler.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Sebuah model ilmiah berguna jika …",
                "options": [
                    "Indah dan kompleks",
                    "Mampu menghasilkan prediksi yang cocok dengan data",
                    "Selalu benar di semua konteks",
                    "Tidak memerlukan asumsi"
                ],
                "correct_index": 1,
                "explanation": "Nilai model diukur dari kekuatan prediksi dan kesesuaiannya dengan pengamatan dalam batas asumsi yang dinyatakan.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pada tingkat sel, contoh keterkaitan struktur–fungsi adalah …",
                "options": [
                    "Membran plasma cair sehingga tidak selektif",
                    "Mikrotubulus yang kaku memungkinkan transport vesikel terarah",
                    "Ribosom besar agar tidak efisien",
                    "Nukleus tanpa pori untuk melindungi DNA"
                ],
                "correct_index": 1,
                "explanation": "Mikrotubulus menyediakan rel untuk motor protein (kinesin/dinein) sehingga vesikel bergerak terarah; membran tetap selektif meski cair.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pernyataan benar tentang data dan inferensi …",
                "options": [
                    "Data adalah interpretasi; inferensi adalah pengukuran",
                    "Data adalah hasil pengamatan/pengukuran; inferensi adalah kesimpulan yang ditarik dari data",
                    "Inferensi selalu objektif",
                    "Data hanya valid jika mendukung hipotesis"
                ],
                "correct_index": 1,
                "explanation": "Data dapat bersifat kualitatif/kuantitatif; inferensi menautkan data dengan hipotesis/teori; keduanya bisa bias bila metodologi lemah.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Dalam kerangka homeostasis, titik setel (set point) adalah …",
                "options": [
                    "Nilai referensi yang ditargetkan oleh sistem pengatur",
                    "Nilai variabel bebas",
                    "Hasil pengukuran acak",
                    "Batas maksimum biologis"
                ],
                "correct_index": 0,
                "explanation": "Sistem umpan balik negatif berupaya mempertahankan variabel (misal suhu tubuh) dekat titik setel melalui sensor–integrator–efektor.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Konsep ‘emergent properties’ berarti …",
                "options": [
                    "Sifat bagian sama persis dengan sifat keseluruhan",
                    "Sifat baru muncul pada tingkat organisasi lebih tinggi akibat interaksi komponen",
                    "Sifat menurun saat tingkat organisasi meningkat",
                    "Sifat hanya ada pada tingkat molekuler"
                ],
                "correct_index": 1,
                "explanation": "Interaksi komponen menghasilkan perilaku/sifat yang tidak tampak pada bagian terpisah, misalnya kesadaran dari jaringan saraf.",
                "difficulty": "OSN-N"
            },
            {
                "chapter_id": cid,
                "question": "Pemilihan acak (randomization) dalam eksperimen bertujuan untuk …",
                "options": [
                    "Memastikan semua kelompok identik",
                    "Mengurangi bias sistematis dalam penempatan perlakuan",
                    "Meningkatkan variabel pengganggu",
                    "Menghilangkan kebutuhan kontrol"
                ],
                "correct_index": 1,
                "explanation": "Randomisasi menyebarkan faktor perancu tak terukur secara merata antar kelompok sehingga bias sistematis berkurang.",
                "difficulty": "OSN-N"
            }
        ]

        # If fewer than needed remain to reach 20, take that many from questions
        to_insert = max(0, 20 - existing_q)
        if to_insert > 0:
            payloads = questions[:to_insert]
            inserted = 0
            ids: List[str] = []
            for q in payloads:
                new_id = create_document("quizquestion", q)
                ids.append(new_id)
                inserted += 1
            return {
                "chapter_id": str(chapter_doc["_id"]),
                "chapter_number": chapter_doc.get("number"),
                "chapter_title": chapter_doc.get("title"),
                "existing_questions": existing_q,
                "inserted": inserted,
                "total_now": existing_q + inserted
            }

    return {
        "chapter_id": str(chapter_doc["_id"]),
        "chapter_number": chapter_doc.get("number"),
        "chapter_title": chapter_doc.get("title"),
        "existing_questions": existing_q,
        "inserted": 0,
        "total_now": existing_q
    }


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
