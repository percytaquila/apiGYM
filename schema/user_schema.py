from pydantic import BaseModel

class UserSchema(BaseModel):
    nombre: str
    apellido: str
    email: str
    password_hash: str