from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Literal, Dict, Any

class Axis(str, Enum):
    GROUNDING = "grounding"
    COHERENCE = "coherence"
    PREDICTIVE = "predictive"
    HUMAN = "human"

class Triple(BaseModel):
    model: str
    task: str
    score: float = Field(..., ge=0.0, le=1.0)
    axis: Axis
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    submitter: str = "realityinspector"
    version: str = "0.1.0"
    evidence: Dict[str, Any] = Field(default_factory=dict)
    run_hash: str = Field(..., min_length=64, max_length=64)  # sha256

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
