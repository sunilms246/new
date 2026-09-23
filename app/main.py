"""
FastAPI Backend Application Entry Point
HTTP Error Defect Report Generator (RAG-based)
TCS Technology Day - IT Quality Assurance Track
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.models import DefectRequest, DefectReportResponse
from app.generator import get_generator
from app.mdn_data import get_mdn_loader

app = FastAPI(
    title="HTTP Error Defect Report Generator (RAG-based)",
    description="RAG-powered defect report generation using MDN HTTP Status docs for TCS Tech Day QA Track",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
generator = get_generator()
mdn_loader = get_mdn_loader()

@app.post("/api/generate", response_model=DefectReportResponse)
async def generate_defect_report(request: DefectRequest):
    if not request.raw_input or not request.raw_input.strip():
        raise HTTPException(status_code=400, detail="Raw defect input text cannot be empty.")
    
    try:
        report = generator.generate_report(
            raw_input=request.raw_input.strip(),
            selected_code=request.selected_code
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@app.get("/api/status-codes")
async def get_status_codes():
    """Returns list of supported HTTP status codes and details."""
    return mdn_loader.get_all()

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "HTTP Error Defect Report Generator",
        "vector_store_active": True,
        "mdn_dataset_size": len(mdn_loader.get_all())
    }

# Serve static frontend files (mounted at root so relative css/js paths resolve;
# /api routes declared above take precedence).
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
