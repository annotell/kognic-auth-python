from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ApiCredentials:
    client_id: str
    client_secret: str
    email: str
    user_id: int
    issuer: str
    name: str = "API Credentials"
    created: Optional[datetime] = None
    expires: Optional[datetime] = None
    scopes: List[str] = field(default_factory=list)
