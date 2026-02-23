from dataclasses import dataclass


@dataclass
class ApiCredentials:
    client_id: str
    client_secret: str
    email: str
    user_id: int
    issuer: str
    name: str = "API Credentials"
