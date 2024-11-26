from pydantic import BaseModel

class LoginSchema(BaseModel):
    email: str
    password_hash: str
