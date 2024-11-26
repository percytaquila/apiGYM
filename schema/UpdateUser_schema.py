from pydantic import BaseModel

class UpdateUserSchema(BaseModel):
    usuario_id: int
    objetivo: str = None
    nivel_experiencia: str = None