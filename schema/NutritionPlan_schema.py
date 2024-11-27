from pydantic import BaseModel

class NutritionPlanRequest(BaseModel):
    id_usuario: int
    genero: str
    edad: int
    peso_actual: float
    altura: float
    nivel_experiencia: str
    objetivo: str