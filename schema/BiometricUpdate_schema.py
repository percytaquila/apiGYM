from pydantic import BaseModel
from typing import Optional

class BiometricUpdateSchema(BaseModel):
    genero: Optional[str] = None
    edad: Optional[int] = None
    altura: Optional[float] = None
    peso_actual: Optional[float] = None
    objetivo: Optional[str] = None
    nivel_experiencia: Optional[str] = None
    vector_biometrico: Optional[str] = None
    datos_completos: Optional[bool] = None