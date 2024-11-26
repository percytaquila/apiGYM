from pydantic import BaseModel

class ProgressSchema(BaseModel):
    usuario_id: int
    ejercicio_id: int
    repeticiones: int
    peso: float = None