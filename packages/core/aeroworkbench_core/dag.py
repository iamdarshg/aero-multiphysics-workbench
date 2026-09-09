from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class ComputationNode(BaseModel):
    model_config = ConfigDict(frozen=True)
    node_type: str
    inputs: dict[str, Any]
    dependencies: dict[str, str]
    implementation_version: str

    @property
    def cache_key(self) -> str:
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
