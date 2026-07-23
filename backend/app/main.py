# backend/app/main.py
# ============================================================
# FastAPI Backend — TAU (Transaction Agent Ultimate)
#   core.py         -> /api/journal, /api/term
#   files.py        -> /api/analyze-file
#   reconcile.py    -> /api/reconcile/*
#   history.py      -> /api/history/*        (shared Work History archive)
#   pdf.py          -> /api/pdf/*            (shared PDF ingestion service)
#   consolidated.py -> /api/consolidated/*   (Consolidated Workbook add-on)
# ============================================================

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db

from app.routers import core, files, reconcile, history, pdf, consolidated, chat, gl_review

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Accounting Transaction Agent API (TAU)",
    description="AI-powered accounting utility hub",
    version="0.9.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "TAU API is running", "version": "0.8.0"}


app.include_router(core.router)
app.include_router(files.router)
app.include_router(reconcile.router)
app.include_router(history.router)
app.include_router(pdf.router)
app.include_router(consolidated.router)
app.include_router(chat.router)
app.include_router(gl_review.router)