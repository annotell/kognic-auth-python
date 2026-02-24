from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
