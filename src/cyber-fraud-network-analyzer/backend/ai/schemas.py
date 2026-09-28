"""
ai/schemas.py
Pydantic models for AI extraction I/O — strict, validated, serialisable.

Entity types    : PERSON PHONE SIM DEVICE IMEI BANK_ACCOUNT UPI_ID
                  TRANSACTION VICTIM SUSPECT LOCATION IP_ADDRESS
                  CASE ORGANIZATION EVIDENCE

Relationship types: OWNS USES CONTROLS CALLED TRANSFERRED_TO PAID_TO
                    ASSOCIATED_WITH USED_DEVICE REGISTERED_TO LOCATED_AT
                    INVOLVED_IN VICTIM_OF SUSPECTED_IN PART_OF

Evidence source tags:
  observed     — directly stated / copied verbatim from input text
  inferred     — logically derived from multiple observed facts
  ai_generated — LLM interpretation with no verbatim anchor in input
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Controlled vocabularies ──────────────────────────────────────────────────

class EntityType(str, Enum):
    PERSON       = "PERSON"
    PHONE        = "PHONE"
    SIM          = "SIM"
    DEVICE       = "DEVICE"
    IMEI         = "IMEI"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    UPI_ID       = "UPI_ID"
    TRANSACTION  = "TRANSACTION"
    VICTIM       = "VICTIM"
    SUSPECT      = "SUSPECT"
    LOCATION     = "LOCATION"
    IP_ADDRESS   = "IP_ADDRESS"
    CASE         = "CASE"
    ORGANIZATION = "ORGANIZATION"
    EVIDENCE     = "EVIDENCE"


class RelationshipType(str, Enum):
    OWNS            = "OWNS"
    USES            = "USES"
    CONTROLS        = "CONTROLS"
    CALLED          = "CALLED"
    TRANSFERRED_TO  = "TRANSFERRED_TO"
    PAID_TO         = "PAID_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    USED_DEVICE     = "USED_DEVICE"
    REGISTERED_TO   = "REGISTERED_TO"
    LOCATED_AT      = "LOCATED_AT"
    INVOLVED_IN     = "INVOLVED_IN"
    VICTIM_OF       = "VICTIM_OF"
    SUSPECTED_IN    = "SUSPECTED_IN"
    PART_OF         = "PART_OF"


class EvidenceSource(str, Enum):
    OBSERVED     = "observed"       # verbatim / directly stated in input
    INFERRED     = "inferred"       # logically derived from observed facts
    AI_GENERATED = "ai_generated"   # LLM interpretation without verbatim anchor


# ── Entity model ─────────────────────────────────────────────────────────────

class ExtractedEntity(BaseModel):
    entity_id:      str        = Field(..., description="Unique ID, e.g. ent_<hex>")
    type:           EntityType
    value:          str        = Field(..., min_length=1, description="Normalised canonical value")
    raw_value:      str        = Field(..., description="Original value from input before normalisation")
    confidence:     float      = Field(..., ge=0.0, le=1.0)
    evidence_id:    Optional[str] = None
    case_id:        Optional[str] = None
    source_text:    Optional[str] = Field(None, description="Verbatim snippet from input that supports this entity")
    evidence_source: EvidenceSource = EvidenceSource.OBSERVED
    attributes:     dict[str, Any] = Field(default_factory=dict)
    extracted_at:   Optional[str]  = None

    @field_validator("value")
    @classmethod
    def strip_value(cls, v: str) -> str:
        return v.strip()

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)

    def dedup_key(self) -> str:
        """Canonical key used for deduplication — (type, normalised value)."""
        return f"{self.type.value}::{self.value.upper()}"


# ── Relationship model ────────────────────────────────────────────────────────

class ExtractedRelationship(BaseModel):
    relationship_id: str      = Field(..., description="Unique ID, e.g. rel_<hex>")
    source_entity:   str      = Field(..., description="entity_id of source")
    relationship:    RelationshipType
    target_entity:   str      = Field(..., description="entity_id of target")
    confidence:      float    = Field(..., ge=0.0, le=1.0)
    evidence_id:     Optional[str] = None
    case_id:         Optional[str] = None
    source_text:     Optional[str] = None
    evidence_source: EvidenceSource = EvidenceSource.OBSERVED
    attributes:      dict[str, Any] = Field(default_factory=dict)
    extracted_at:    Optional[str]  = None

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)

    def dedup_key(self) -> str:
        return f"{self.source_entity}::{self.relationship.value}::{self.target_entity}"


# ── LLM I/O envelopes ────────────────────────────────────────────────────────

class ExtractionRequest(BaseModel):
    """Input to the extraction pipeline."""
    text:        str = Field(..., min_length=1, description="Raw intelligence / narrative text")
    case_id:     Optional[str] = None
    evidence_id: Optional[str] = None
    source_hint: Optional[str] = Field(
        None,
        description="Optional hint about the source type: complaint | call_record | transaction_log | …",
    )
    max_entities:      int   = Field(default=100, ge=1, le=500)
    max_relationships: int   = Field(default=200, ge=1, le=1000)
    min_confidence:    float = Field(default=0.3, ge=0.0, le=1.0)

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be empty or whitespace only")
        return v


class ExtractionResult(BaseModel):
    """Full result returned by the extraction pipeline."""
    request_id:    str
    case_id:       Optional[str]
    evidence_id:   Optional[str]
    entities:      list[ExtractedEntity]       = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    new_entities:       int = 0
    merged_entities:    int = 0
    new_relationships:  int = 0
    merged_relationships: int = 0
    provider:      str
    model:         Optional[str] = None
    extracted_at:  str
    warnings:      list[str] = Field(default_factory=list)
