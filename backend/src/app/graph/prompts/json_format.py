from __future__ import annotations

import json
from typing import Any


def compact_json(value: Any) -> str:
    """Serialize prompt data without token-wasting optional whitespace."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
