"""
ai/provider.py
AI provider abstraction for entity and relationship extraction.

Providers available:
  mock    — deterministic regex/rule-based extractor (default, no API key needed)
  watsonx — IBM watsonx.ai  (requires WATSONX_API_KEY + WATSONX_PROJECT_ID)

Switch providers by setting AI_PROVIDER in .env.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from config.settings import (
    AI_PROVIDER,
    WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL, WATSONX_MODEL_ID,
)

# ── Base contract ─────────────────────────────────────────────────────────────

class BaseAIProvider(ABC):
    """
    All provider implementations must honour this contract.
    Both methods return raw dicts matching the ExtractedEntity /
    ExtractedRelationship schema (without entity_id / relationship_id —
    those are assigned by the extraction service after deduplication).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in results, e.g. 'mock', 'watsonx', 'openai'."""

    @property
    def model_id(self) -> str | None:
        return None

    @abstractmethod
    def extract_entities_raw(self, text: str, context: dict[str, Any]) -> list[dict]:
        """
        Return a list of raw entity dicts:
          { type, value, raw_value, confidence, source_text, evidence_source, attributes }
        The service will assign entity_id, validate, normalise, and deduplicate.
        """

    @abstractmethod
    def extract_relationships_raw(
        self, text: str, entities: list[dict], context: dict[str, Any]
    ) -> list[dict]:
        """
        Return a list of raw relationship dicts:
          { source_value, source_type, relationship, target_value, target_type,
            confidence, source_text, evidence_source, attributes }
        The service resolves source/target to entity_ids.
        """

    def generate_summary(self, case_data: dict) -> str:
        return (
            f"[{self.name}] Investigation summary for case "
            f"{case_data.get('id', 'unknown')} — AI summary not yet configured."
        )


# ═════════════════════════════════════════════════════════════════════════════
# MOCK PROVIDER
# Deterministic rule-based extractor — useful for tests and offline dev.
# Extracts real entities from text using regex patterns; never invents.
# ═════════════════════════════════════════════════════════════════════════════

# Compiled patterns (order matters — more specific first)
_RE_PHONE    = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")
_RE_IMEI     = re.compile(r"\b\d{15}\b")
_RE_ICCID    = re.compile(r"\b89\d{17,18}\b")
_RE_IMSI     = re.compile(r"\b404\d{10,12}\b")
_RE_ACCOUNT  = re.compile(r"\b\d{9,18}\b")
_RE_IFSC     = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_RE_UPI      = re.compile(r"\b[\w.\-]+@(?:okaxis|oksbi|okicici|okhdfcbank|ybl|ibl|paytm|upi|apl|axl)\b", re.IGNORECASE)
_RE_IP       = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_AMOUNT   = re.compile(r"(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d{1,2})?", re.IGNORECASE)
_RE_TXNID    = re.compile(r"\b(?:TXN|UTR|IMPS|NEFT|UPI)[A-Z0-9]{8,20}\b", re.IGNORECASE)
_RE_CASE     = re.compile(r"\b(?:FIR|CMP|CASE)[/\-]\d{3,}[/\-]\d{4}\b", re.IGNORECASE)
_RE_IP_RANGE = re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d+\.\d+\b")
_RE_NAME     = re.compile(
    r"\b(?:accused|suspect|victim|complainant|named|person|individual|called|Mr\.?|Ms\.?|Mrs\.?|Sh\.?|Smt\.?)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
)
_RE_ORG      = re.compile(
    r"\b((?:[A-Z][A-Za-z&\s]+)\s+(?:Ltd|Limited|Pvt|Private|Bank|Finance|Insurance|Corp|Corporation|"
    r"Agency|Bureau|Foundation|Trust|Co\.))\b"
)
_RE_LOCATION = re.compile(
    r"\b(?:at|in|from|near|located at)\s+([A-Z][a-zA-Z\s,]{4,60}?)(?:\.|,|;|\n|$)"
)


def _strip_amount(s: str) -> str:
    return re.sub(r"[₹,\s]|Rs\.?|INR", "", s, flags=re.IGNORECASE).strip()


class MockAIProvider(BaseAIProvider):
    """
    Deterministic regex-based extractor.
    Entities are only emitted when the pattern fires — no hallucination.
    Confidence values are fixed per pattern type.
    """

    @property
    def name(self) -> str:
        return "mock"

    def extract_entities_raw(self, text: str, context: dict[str, Any]) -> list[dict]:
        found: list[dict] = []

        def add(type_: str, value: str, raw: str, conf: float, snippet: str,
                source: str = "observed", attrs: dict | None = None):
            found.append({
                "type":            type_,
                "value":           value,
                "raw_value":       raw,
                "confidence":      conf,
                "source_text":     snippet[:200],
                "evidence_source": source,
                "attributes":      attrs or {},
            })

        # Phones (before IMEI to avoid 15-digit confusion)
        for m in _RE_PHONE.finditer(text):
            num = re.sub(r"[\s\-]", "", m.group())
            add("PHONE", num, m.group(), 0.92, m.group())

        # IMEI — 15 digits, not already captured as phone
        captured_phones = {re.sub(r"[\s\-]", "", m.group()) for m in _RE_PHONE.finditer(text)}
        for m in _RE_IMEI.finditer(text):
            if m.group() not in captured_phones:
                add("IMEI", m.group(), m.group(), 0.88, m.group(),
                    attrs={"digits": 15})

        # SIM — ICCID
        for m in _RE_ICCID.finditer(text):
            add("SIM", m.group(), m.group(), 0.85, m.group(),
                attrs={"field": "iccid"})

        # UPI IDs
        for m in _RE_UPI.finditer(text):
            add("UPI_ID", m.group().lower(), m.group(), 0.95, m.group())

        # IFSC — hints at bank account
        for m in _RE_IFSC.finditer(text):
            add("BANK_ACCOUNT", m.group().upper(), m.group(), 0.72, m.group(),
                attrs={"field": "ifsc_code"})

        # Transaction IDs
        for m in _RE_TXNID.finditer(text):
            add("TRANSACTION", m.group().upper(), m.group(), 0.89, m.group())

        # FIR / Case references
        for m in _RE_CASE.finditer(text):
            add("CASE", m.group().upper(), m.group(), 0.93, m.group())

        # IP addresses (public only; skip RFC-1918 ranges)
        for m in _RE_IP.finditer(text):
            if not _RE_IP_RANGE.match(m.group()):
                add("IP_ADDRESS", m.group(), m.group(), 0.82, m.group())

        # Named persons
        for m in _RE_NAME.finditer(text):
            name = m.group(1).strip()
            role = m.group(0).split()[0].lower().rstrip(".")
            etype = "VICTIM" if role in ("victim", "complainant") \
                    else "SUSPECT" if role in ("accused", "suspect") \
                    else "PERSON"
            add(etype, name.title(), name, 0.78, m.group(),
                source="observed", attrs={"role_hint": role})

        # Organisations
        for m in _RE_ORG.finditer(text):
            add("ORGANIZATION", m.group(1).strip(), m.group(1), 0.71,
                m.group(), source="observed")

        # Locations — inferred (lower confidence)
        for m in _RE_LOCATION.finditer(text):
            loc = m.group(1).strip().rstrip(",;.")
            if len(loc) > 3:
                add("LOCATION", loc.title(), loc, 0.65, m.group(),
                    source="inferred")

        return found

    def extract_relationships_raw(
        self, text: str, entities: list[dict], context: dict[str, Any]
    ) -> list[dict]:
        """
        Build relationships from co-occurrence in text.
        Only emits relationships that are grounded in the entity list.
        """
        rels: list[dict] = []

        # Index entities by type for quick look-up
        by_type: dict[str, list[dict]] = {}
        for e in entities:
            by_type.setdefault(e["type"], []).append(e)

        def add_rel(src: dict, rel: str, tgt: dict, conf: float,
                    snippet: str, source: str = "inferred"):
            rels.append({
                "source_value":    src["value"],
                "source_type":     src["type"],
                "relationship":    rel,
                "target_value":    tgt["value"],
                "target_type":     tgt["type"],
                "confidence":      conf,
                "source_text":     snippet[:200],
                "evidence_source": source,
                "attributes":      {},
            })

        persons  = by_type.get("PERSON", []) + by_type.get("SUSPECT", []) + by_type.get("VICTIM", [])
        phones   = by_type.get("PHONE", [])
        accounts = by_type.get("BANK_ACCOUNT", [])
        upis     = by_type.get("UPI_ID", [])
        imeis    = by_type.get("IMEI", [])
        txns     = by_type.get("TRANSACTION", [])
        cases    = by_type.get("CASE", [])
        locs     = by_type.get("LOCATION", [])

        # PERSON owns PHONE — co-occurrence within 150 chars
        for person in persons:
            for phone in phones:
                idx_p = text.find(person["raw_value"])
                idx_ph = text.find(phone["raw_value"])
                if idx_p >= 0 and idx_ph >= 0 and abs(idx_p - idx_ph) < 150:
                    snippet = text[min(idx_p, idx_ph):max(idx_p, idx_ph) + 20]
                    add_rel(person, "OWNS", phone, 0.72, snippet)

        # PERSON owns BANK_ACCOUNT
        for person in persons:
            for acc in accounts:
                idx_p = text.find(person["raw_value"])
                idx_a = text.find(acc["raw_value"])
                if idx_p >= 0 and idx_a >= 0 and abs(idx_p - idx_a) < 200:
                    add_rel(person, "OWNS", acc, 0.68,
                            text[min(idx_p, idx_a):max(idx_p, idx_a) + 20])

        # PERSON owns UPI_ID
        for person in persons:
            for upi in upis:
                idx_p = text.find(person["raw_value"])
                idx_u = text.find(upi["raw_value"])
                if idx_p >= 0 and idx_u >= 0 and abs(idx_p - idx_u) < 200:
                    add_rel(person, "OWNS", upi, 0.75,
                            text[min(idx_p, idx_u):max(idx_p, idx_u) + 20])

        # PERSON USED_DEVICE IMEI
        for person in persons:
            for imei in imeis:
                idx_p  = text.find(person["raw_value"])
                idx_im = text.find(imei["raw_value"])
                if idx_p >= 0 and idx_im >= 0 and abs(idx_p - idx_im) < 250:
                    add_rel(person, "USED_DEVICE", imei, 0.66,
                            text[min(idx_p, idx_im):max(idx_p, idx_im) + 20])

        # PERSON INVOLVED_IN CASE
        for person in persons:
            for case in cases:
                etype = person["type"]
                rel = "VICTIM_OF"  if etype == "VICTIM"  else \
                      "SUSPECTED_IN" if etype == "SUSPECT" else \
                      "INVOLVED_IN"
                add_rel(person, rel, case, 0.80, f"{person['value']} {case['value']}")

        # PHONE CALLED PHONE — look for "called" between two phone numbers
        if len(phones) >= 2:
            for m in re.finditer(r"(\d{10})\s+(?:called|contacted|rang)\s+(\d{10})", text):
                src_num = m.group(1)
                tgt_num = m.group(2)
                src_e = next((p for p in phones if p["value"] == src_num), None)
                tgt_e = next((p for p in phones if p["value"] == tgt_num), None)
                if src_e and tgt_e:
                    add_rel(src_e, "CALLED", tgt_e, 0.91, m.group(), source="observed")

        # UPI TRANSFERRED_TO BANK_ACCOUNT
        for upi in upis:
            for acc in accounts:
                idx_u = text.find(upi["raw_value"])
                idx_a = text.find(acc["raw_value"])
                if idx_u >= 0 and idx_a >= 0 and abs(idx_u - idx_a) < 200:
                    add_rel(upi, "TRANSFERRED_TO", acc, 0.69,
                            text[min(idx_u, idx_a):max(idx_u, idx_a) + 20],
                            source="inferred")

        # PERSON LOCATED_AT LOCATION
        for person in persons:
            for loc in locs:
                idx_p = text.find(person["raw_value"])
                idx_l = text.find(loc["raw_value"])
                if idx_p >= 0 and idx_l >= 0 and abs(idx_p - idx_l) < 300:
                    add_rel(person, "LOCATED_AT", loc, 0.61,
                            text[min(idx_p, idx_l):max(idx_p, idx_l) + 20],
                            source="inferred")

        # TRANSACTION PART_OF CASE
        for txn in txns:
            for case in cases:
                idx_t = text.find(txn["raw_value"])
                idx_c = text.find(case["raw_value"])
                if idx_t >= 0 and idx_c >= 0 and abs(idx_t - idx_c) < 500:
                    snippet = text[min(idx_t, idx_c):max(idx_t, idx_c) + 20]
                    add_rel(txn, "PART_OF", case, 0.77, snippet, source="inferred")

        return rels

    def generate_summary(self, case_data: dict) -> str:
        title = case_data.get("title", "unknown case")
        return (
            f"[Mock AI Summary] Case: {title}. "
            f"Pattern: {case_data.get('fraud_pattern', 'unknown')}. "
            f"Severity: {case_data.get('severity', 'unknown')}. "
            f"This is a deterministic mock summary — configure a real AI provider "
            f"(AI_PROVIDER=watsonx) for LLM-generated summaries."
        )


# ═════════════════════════════════════════════════════════════════════════════
# WATSONX PROVIDER STUB
# ═════════════════════════════════════════════════════════════════════════════

WATSONX_ENTITY_PROMPT = """You are a forensic intelligence analyst. Extract all entities from the text below.

Return ONLY a valid JSON object with this exact structure:
{{
  "entities": [
    {{
      "type": "<ENTITY_TYPE>",
      "value": "<canonical value>",
      "raw_value": "<exact text from input>",
      "confidence": <0.0-1.0>,
      "source_text": "<verbatim snippet>",
      "evidence_source": "observed|inferred|ai_generated",
      "attributes": {{}}
    }}
  ]
}}

Valid entity types: PERSON PHONE SIM DEVICE IMEI BANK_ACCOUNT UPI_ID TRANSACTION
                    VICTIM SUSPECT LOCATION IP_ADDRESS CASE ORGANIZATION EVIDENCE

Rules:
- Only extract entities that appear in or are directly supported by the text.
- Do NOT invent entities.
- evidence_source must be "observed" if the value appears verbatim in the text,
  "inferred" if logically derived, "ai_generated" if interpreted.
- confidence reflects extraction certainty (0.0–1.0).

Text:
{text}"""

WATSONX_REL_PROMPT = """You are a forensic intelligence analyst. Extract relationships between the given entities.

Entities (JSON):
{entities_json}

Return ONLY a valid JSON object:
{{
  "relationships": [
    {{
      "source_value": "<entity value>",
      "source_type":  "<entity type>",
      "relationship": "<RELATIONSHIP_TYPE>",
      "target_value": "<entity value>",
      "target_type":  "<entity type>",
      "confidence": <0.0-1.0>,
      "source_text": "<supporting snippet>",
      "evidence_source": "observed|inferred|ai_generated",
      "attributes": {{}}
    }}
  ]
}}

Valid relationship types: OWNS USES CONTROLS CALLED TRANSFERRED_TO PAID_TO
                          ASSOCIATED_WITH USED_DEVICE REGISTERED_TO LOCATED_AT
                          INVOLVED_IN VICTIM_OF SUSPECTED_IN PART_OF

Rules:
- Only emit relationships grounded in the text or logically required.
- Do NOT invent relationships.

Text:
{text}"""


class WatsonxAIProvider(BaseAIProvider):
    """
    IBM watsonx.ai provider via REST API.
    Requires: WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL, WATSONX_MODEL_ID
    """

    def __init__(self):
        if not WATSONX_API_KEY:
            raise RuntimeError(
                "WATSONX_API_KEY is not set. "
                "Configure it in .env or use AI_PROVIDER=mock."
            )
        if not WATSONX_PROJECT_ID:
            raise RuntimeError(
                "WATSONX_PROJECT_ID is not set. "
                "Configure it in .env or use AI_PROVIDER=mock."
            )
        self._api_key    = WATSONX_API_KEY
        self._project_id = WATSONX_PROJECT_ID
        self._url        = WATSONX_URL
        self._model      = WATSONX_MODEL_ID
        self._token: str | None = None

    @property
    def name(self) -> str:
        return "watsonx"

    @property
    def model_id(self) -> str | None:
        return self._model

    def _iam_token(self) -> str:
        """Exchange API key for a short-lived IAM bearer token."""
        import urllib.request, urllib.parse
        if self._token:
            return self._token
        data = urllib.parse.urlencode({
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": self._api_key,
        }).encode()
        req = urllib.request.Request(
            "https://iam.cloud.ibm.com/identity/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            self._token = json.loads(resp.read())["access_token"]
        return self._token

    def _call_llm(self, prompt: str) -> str:
        import urllib.request
        payload = json.dumps({
            "model_id": self._model,
            "input":    prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens":  2048,
                "temperature":     0.0,
            },
            "project_id": self._project_id,
        }).encode()
        url = f"{self._url}/ml/v1/text/generation?version=2023-05-29"
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {self._iam_token()}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        return result["results"][0]["generated_text"].strip()

    def _parse_llm_json(self, raw: str, key: str) -> list[dict]:
        # Strip markdown code fences if present
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        try:
            parsed = json.loads(raw)
            return parsed.get(key, [])
        except json.JSONDecodeError:
            # Try to extract the first JSON object
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group()).get(key, [])
                except json.JSONDecodeError:
                    pass
        return []

    def extract_entities_raw(self, text: str, context: dict[str, Any]) -> list[dict]:
        prompt = WATSONX_ENTITY_PROMPT.format(text=text[:4000])
        raw = self._call_llm(prompt)
        return self._parse_llm_json(raw, "entities")

    def extract_relationships_raw(
        self, text: str, entities: list[dict], context: dict[str, Any]
    ) -> list[dict]:
        entities_json = json.dumps(
            [{"type": e["type"], "value": e["value"]} for e in entities[:50]],
            indent=2,
        )
        prompt = WATSONX_REL_PROMPT.format(
            entities_json=entities_json, text=text[:4000]
        )
        raw = self._call_llm(prompt)
        return self._parse_llm_json(raw, "relationships")


# ═════════════════════════════════════════════════════════════════════════════
# FACTORY
# ═════════════════════════════════════════════════════════════════════════════

def get_provider() -> BaseAIProvider:
    """Return the configured AI provider instance."""
    provider = AI_PROVIDER.lower()
    if provider == "mock":
        return MockAIProvider()
    if provider == "watsonx":
        return WatsonxAIProvider()
    raise ValueError(
        f"Unknown AI_PROVIDER: {AI_PROVIDER!r}. "
        "Valid values: mock | watsonx"
    )
