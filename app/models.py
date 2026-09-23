"""
Pydantic Data Schemas for HTTP Error Defect Report Generator
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DefectRequest(BaseModel):
    raw_input: str = Field(..., description="Raw vague defect description typed by QA engineer (e.g. 'login problem', '404')")
    selected_code: Optional[int] = Field(None, description="Optional manually selected HTTP status code to override auto-detection")

class CandidateCode(BaseModel):
    code: int
    name: str
    category: str
    score: float
    match_type: str  # "regex", "keyword", "semantic"

class TransparencyInfo(BaseModel):
    detected_code: Optional[int]
    detected_name: Optional[str]
    match_reason: str
    retrieved_chunk: str
    mdn_url: Optional[str]
    attribution: str = "MDN Web Docs (CC-BY-SA 2.5)"
    latency_ms: float
    candidates: List[CandidateCode] = []

class DefectReportResponse(BaseModel):
    raw_input: str
    title: str
    likely_cause: str
    steps_to_reproduce: List[str]
    expected_result: str
    actual_result: str
    suggested_severity: str
    severity_rationale: str
    developer_remediation: str
    is_http_grounded: bool
    transparency: TransparencyInfo
