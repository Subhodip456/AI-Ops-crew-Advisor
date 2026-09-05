from pydantic import BaseModel
from typing import Optional, Any

class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, Any]] = []

class EligibilityRequest(BaseModel):
    crew_id: str
    pairing_id: str

class DisruptionRequest(BaseModel):
    crew_id: str
    date: str
    pairing_id: Optional[str] = None
