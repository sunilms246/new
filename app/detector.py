"""
HTTP Status Code Detector Module
Maps raw free-text defect descriptions to candidate HTTP status codes using regex, keyword rules, and semantic fallback.
"""

import os
import re
from typing import List, Tuple, Dict, Any, Optional
from app.mdn_data import get_mdn_loader
from app.models import CandidateCode

class StatusCodeDetector:
    def __init__(self):
        self.mdn_loader = get_mdn_loader()

    def detect(self, text: str, manual_override: Optional[int] = None) -> Tuple[Optional[int], str, List[CandidateCode]]:
        """
        Detects HTTP status code(s) from input text.
        Returns: (primary_code, reasoning_string, list_of_candidates)
        """
        all_docs = self.mdn_loader.get_all()
        candidates: List[CandidateCode] = []
        text_lower = text.lower().strip()

        # Manual Override Check
        if manual_override is not None:
            matched_item = self.mdn_loader.get_by_code(manual_override)
            if matched_item:
                candidates.append(CandidateCode(
                    code=matched_item["code"],
                    name=matched_item["name"],
                    category=matched_item["category"],
                    score=1.0,
                    match_type="manual_override"
                ))
                return manual_override, f"Manually selected status code {manual_override} ({matched_item['name']}).", candidates

        # 1. Regex Exact Code Match (e.g., "404", "getting 500 error", "http 401")
        code_matches = re.findall(r'\b(1\d\d|2\d\d|3\d\d|4\d\d|5\d\d)\b', text)
        for code_str in code_matches:
            c = int(code_str)
            item = self.mdn_loader.get_by_code(c)
            if item:
                candidates.append(CandidateCode(
                    code=item["code"],
                    name=item["name"],
                    category=item["category"],
                    score=0.98,
                    match_type="regex"
                ))

        # 2. Keyword & Synonym Matching
        keyword_scores: Dict[int, float] = {}
        matched_kw_map: Dict[int, List[str]] = {}

        for item in all_docs:
            code = item["code"]
            kws = item.get("keywords", [])
            score = 0.0
            matched_words = []

            for kw in kws:
                if kw in text_lower:
                    # Longer matching keyword gets higher score
                    kw_weight = 0.4 + min(len(kw) * 0.05, 0.5)
                    score += kw_weight
                    matched_words.append(kw)

            if score > 0:
                keyword_scores[code] = min(score, 0.95)
                matched_kw_map[code] = matched_words

        # Add keyword candidates if not already added by regex
        existing_codes = {c.code for c in candidates}
        sorted_kw = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)

        for code, score in sorted_kw:
            if code not in existing_codes:
                item = self.mdn_loader.get_by_code(code)
                if item:
                    candidates.append(CandidateCode(
                        code=item["code"],
                        name=item["name"],
                        category=item["category"],
                        score=round(score, 2),
                        match_type="keyword"
                    ))

        # Sort candidates by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)

        if candidates:
            primary = candidates[0]
            if primary.match_type == "regex":
                reason = f"Explicitly detected HTTP status code {primary.code} from text input via regex."
            elif primary.match_type == "keyword":
                kw_str = ", ".join(matched_kw_map.get(primary.code, []))
                reason = f"Matched to {primary.name} based on keyword(s): '{kw_str}'."
            else:
                reason = f"Matched to {primary.name} with score {primary.score}."
            return primary.code, reason, candidates[:5]

        # 3. LLM Semantic Classification Fallback (FR2)
        llm_candidates = self._llm_classify(text, manual_override)
        if llm_candidates:
            return llm_candidates[0].code, f"Matched to {llm_candidates[0].name} via LLM semantic classification of input.", llm_candidates

        # No direct keyword/regex match
        return None, "No specific HTTP status code matched standard keywords or regex patterns in input.", []

    def _llm_classify(self, text: str, manual_override: Optional[int] = None) -> List[CandidateCode]:
        """
        LLM fallback: uses Gemini (if API key configured) to map ambiguous HTTP-ish
        input to a status code. Returns empty list when unavailable or not applicable.
        """
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return []

        # Only use LLM fallback when the text looks plausibly HTTP/web related,
        # to avoid classifying every random QA note into a status code.
        web_signals = re.search(r'(web|http|api|server|page|site|request|response|endpoint|browser|url|response|load|submit|login|auth|error|bug|broken|down|fail)', text.lower())
        if not web_signals:
            return []

        try:
            from google import genai
            import json

            client = genai.Client(api_key=api_key)
            supported = [c["code"] for c in self.mdn_loader.get_all()]
            supported_str = ", ".join(str(c) for c in supported)
            json_shape = '{"code": <integer or null>, "name": <string>}'

            prompt = (
                "You are a QA defect triage assistant. Given a tester's raw defect description, "
                "map it to the most likely HTTP status code.\n\n"
                f"Supported status codes: {supported_str}\n"
                f"Raw description: \"{text}\"\n\n"
                f"Respond with a JSON object matching this shape: {json_shape}. "
                "Return code null if the description cannot be linked to any HTTP error. "
                "Return ONLY valid JSON, no markdown."
            )
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw = response.text.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]

            parsed = json.loads(raw)
            code = parsed.get("code")
            if code is None:
                return []
            item = self.mdn_loader.get_by_code(int(code))
            if item:
                return [CandidateCode(
                    code=item["code"],
                    name=item["name"],
                    category=item["category"],
                    score=0.6,
                    match_type="semantic"
                )]
            return []
        except Exception as e:
            print(f"Detector LLM fallback failed or skipped: {e}")
            return []

_detector_instance = None

def get_detector() -> StatusCodeDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = StatusCodeDetector()
    return _detector_instance
