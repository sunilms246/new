"""
Defect Report Generator Module
Uses LLM (Google Gemini) when API key is present or intelligent RAG template synthesis to generate structured defect reports.
"""

import os
import time
import json
from typing import Dict, Any, Optional
from app.models import DefectReportResponse, TransparencyInfo, CandidateCode
from app.detector import get_detector
from app.vector_store import get_vector_store

class DefectReportGenerator:
    def __init__(self):
        self.detector = get_detector()
        self.vector_store = get_vector_store()
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def generate_report(self, raw_input: str, selected_code: Optional[int] = None) -> DefectReportResponse:
        start_time = time.time()

        # Step 1: Detect Status Code & Candidates
        detected_code, match_reason, candidates = self.detector.detect(raw_input, manual_override=selected_code)

        # Step 2: RAG Vector Retrieval
        if detected_code:
            retrieved_chunk, mdn_item = self.vector_store.query(query_text=raw_input, target_code=detected_code)
            is_http = True
        else:
            retrieved_chunk, mdn_item = self.vector_store.query(query_text=raw_input)
            is_http = False

        # Step 3: LLM or Grounded RAG Synthesis Generation
        response_data = None
        if self.gemini_api_key:
            response_data = self._call_gemini_llm(raw_input, detected_code, retrieved_chunk, is_http)

        if not response_data:
            response_data = self._generate_grounded_fallback(raw_input, detected_code, mdn_item, is_http)

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        mdn_url = mdn_item.get("mdn_url") if mdn_item else None
        detected_name = mdn_item.get("name") if (mdn_item and is_http) else None

        transparency = TransparencyInfo(
            detected_code=detected_code if is_http else None,
            detected_name=detected_name,
            match_reason=match_reason if is_http else "No specific HTTP status code pattern identified in input. Generated general QA defect report.",
            retrieved_chunk=retrieved_chunk if is_http else "N/A - General Defect Report (Not Grounded in MDN HTTP Status Code)",
            mdn_url=mdn_url if is_http else None,
            attribution="MDN Web Docs (CC-BY-SA 2.5)" if is_http else "General QA Defect Template",
            latency_ms=elapsed_ms,
            candidates=candidates
        )

        return DefectReportResponse(
            raw_input=raw_input,
            title=response_data["title"],
            likely_cause=response_data["likely_cause"],
            steps_to_reproduce=response_data["steps_to_reproduce"],
            expected_result=response_data["expected_result"],
            actual_result=response_data["actual_result"],
            suggested_severity=response_data["suggested_severity"],
            severity_rationale=response_data["severity_rationale"],
            developer_remediation=response_data["developer_remediation"],
            is_http_grounded=is_http,
            transparency=transparency
        )

    def _call_gemini_llm(self, raw_input: str, detected_code: Optional[int], retrieved_chunk: str, is_http: bool) -> Optional[Dict[str, Any]]:
        """Invokes Gemini LLM if API Key is configured."""
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_api_key)
            
            prompt = f"""You are an expert QA Lead generating a structured software defect report.
User Defect Input: "{raw_input}"
Detected HTTP Status Code: {detected_code if is_http else 'None (General Defect)'}

Retrieved MDN Grounding Documentation Chunk:
{retrieved_chunk}

Generate a JSON object with EXACTLY the following keys:
- "title": Concise, actionable defect title including HTTP code if applicable
- "likely_cause": Detailed technical explanation grounded in MDN specification
- "steps_to_reproduce": Array of 3-5 clear step strings for template reproduction
- "expected_result": Standard expected behavior per specification
- "actual_result": Observed defect behavior based on user input
- "suggested_severity": One of ["Critical", "High", "Medium", "Low"]
- "severity_rationale": Rationale for suggested severity
- "developer_remediation": Recommended technical fix/action items for developers

Return ONLY valid raw JSON without markdown backticks.
"""
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except Exception as e:
            print(f"Gemini LLM call failed or skipped: {e}")
            return None

    def _generate_grounded_fallback(self, raw_input: str, detected_code: Optional[int], mdn_item: Optional[Dict[str, Any]], is_http: bool) -> Dict[str, Any]:
        """Generates accurate grounded defect report using MDN dataset specifications."""
        if is_http and mdn_item:
            code = mdn_item["code"]
            name = mdn_item["name"]
            category = mdn_item["category"]
            summary = mdn_item["summary"]
            remediation = mdn_item.get("remediation", "Inspect application logs and network trace.")

            # Severity heuristic based on HTTP category
            if category == "Server Error" or code in [401, 403]:
                severity = "High" if code != 500 else "Critical"
                severity_rationale = f"HTTP {code} ({category}) blocks core application functionality or authentication flow."
            elif code in [404, 408, 429]:
                severity = "Medium"
                severity_rationale = f"HTTP {code} impacts specific feature navigation or API request limits."
            else:
                severity = "Medium"
                severity_rationale = f"Standard client-side HTTP {code} error requires remediation."

            steps = mdn_item.get("recommended_steps", [
                "Open browser and navigate to the application endpoint",
                f"Trigger action corresponding to defect: '{raw_input}'",
                f"Observe DevTools Network tab showing HTTP {name} status code"
            ])

            return {
                "title": f"[{name}] Failure observed during '{raw_input}'",
                "likely_cause": f"{summary} Common causes: " + ", ".join(mdn_item.get("causes", [])[:3]) + ".",
                "steps_to_reproduce": steps,
                "expected_result": f"Application executes successfully returning 200 OK with expected payload.",
                "actual_result": f"Request failed with HTTP {name}. Observed behavior: '{raw_input}'.",
                "suggested_severity": severity,
                "severity_rationale": severity_rationale,
                "developer_remediation": remediation
            }
        else:
            # FR6: General No-Match Defect Handling
            return {
                "title": f"[Defect Report] Issue reported: '{raw_input}'",
                "likely_cause": f"Application issue reported as '{raw_input}'. No matching HTTP status code identified in input.",
                "steps_to_reproduce": [
                    "Open application in web browser",
                    f"Perform steps leading to issue: '{raw_input}'",
                    "Observe unexpected behavior or error display"
                ],
                "expected_result": "Application operates smoothly without errors or visual glitches.",
                "actual_result": f"Issue observed: '{raw_input}'.",
                "suggested_severity": "Medium",
                "severity_rationale": "General functional defect requires triage and detailed step logging by tester.",
                "developer_remediation": "Reproduce reported issue in local/staging environment and check browser console logs."
            }

_generator_instance = None

def get_generator() -> DefectReportGenerator:
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = DefectReportGenerator()
    return _generator_instance
