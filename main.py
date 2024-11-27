import json
from fastapi import FastAPI, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from model.user_connection import UserConnection 
from schema.NutritionPlan_schema import NutritionPlanRequest
from schema.Progress_schema import ProgressSchema
from schema.user_schema import UserSchema
from schema.BiometricUpdate_schema import BiometricUpdateSchema
from schema.login_schema import LoginSchema
from schema.UpdateUser_schema import UpdateUserSchema
from passlib.context import CryptContext
import numpy as np
import face_recognition
import cv2
import cohere

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

COHERE_API_KEY = "mmFhYt9j2DRBpEeTv6MhZn6BmD3tzoFmK05zSpsL" 
co = cohere.Client(COHERE_API_KEY)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
conn = UserConnection()

@app.get("/")
def root():
    return "Test"

@app.post("/api/user/insert")
def insert(user_data: UserSchema):
    data = user_data.model_dump()
    data["password_hash"] = pwd_context.hash(data["password_hash"])
    conn.write(data)
    return {"message": "Usuario creado exitosamente"}

@app.post("/api/user/login")
def login(login_data: LoginSchema):
    user = conn.get_user_by_email(login_data.email)
    if user and pwd_context.verify(login_data.password_hash, user['password_hash']):
        return {"message": "Login exitoso", "user_id": user["id"], "nombre": user["nombre"], "apellido": user["apellido"], "email": user["email"], "datos_completos": user["datos_completos"]}
    raise HTTPException(status_code=401, detail="Credenciales incorrectas")

@app.put("/api/user/update/biometric/{user_id}")
async def update_user(user_id: int, imagen: UploadFile, data: str = Form(...)):
    user = conn.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    parsed_data = BiometricUpdateSchema.model_validate_json(data)
    data_values = parsed_data.model_dump()

    try:
        # Leer la imagen cargada
        imagen_bytes = await imagen.read()
        np_array = np.frombuffer(imagen_bytes, np.uint8)
        imagen_decodificada = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        # Generar vector biométrico
        vectores = face_recognition.face_encodings(imagen_decodificada)
        if not vectores:
            raise HTTPException(status_code=400, detail="No se detectó un rostro en la imagen.")

        vector_biometrico = vectores[0]

        if vector_biometrico.dtype != np.float32:
            vector_biometrico = vector_biometrico.astype(np.float32)
 
        # Validar tamaño del vector biométrico
        if vector_biometrico.shape[0] != 128:
            raise HTTPException(
                status_code=400,
                detail=f"El vector biométrico tiene un tamaño inválido: {vector_biometrico.shape[0]}. Debe tener 128 elementos."
            )

        # Convertir a bytes para almacenar en la base de datos
        vector_biometrico_bytes = vector_biometrico.tobytes()
        data_values["vector_biometrico"] = vector_biometrico_bytes

        # Validar el tipo antes de enviarlo
        if not isinstance(vector_biometrico_bytes, bytes):
            raise HTTPException(status_code=500, detail="El vector biométrico no está en el formato esperado (bytes).")
        
        # Actualizar usuario en la base de datos
        conn.update_user(user_id, data_values)

        return {"message": "Usuario actualizado exitosamente"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el vector biométrico: {str(e)}")
    
@app.get("/api/trainers")
def get_trainers(specialty: str = None):
    try:
        trainers = conn.get_trainers_by_specialty(specialty)
        return JSONResponse(content=trainers, media_type="application/json; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/class-details/{id_horario}")
def get_class_details(id_horario: int):
    try:
        trainer_details = conn.get_class_details_by_schedule(id_horario)        
        if not trainer_details:
            raise HTTPException(status_code=404, detail="Entrenador no encontrado")

        return JSONResponse(content=trainer_details, media_type="application/json; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/exercises/recommendations")
def recommend_exercises(
    user_id: int = Query(..., description="ID del usuario"),
    objective: str = Query(..., description="Objetivo del usuario: Bajar de peso, Ganar masa muscular, Mantenerse en forma"),
    experience_level: str = Query(..., description="Nivel de experiencia: Principiante, Intermedio, Avanzado")
):
    
    level_config = {
        "Principiante": {"days": 3, "exercises_per_day": 6},
        "Intermedio": {"days": 4, "exercises_per_day": 8},
        "Avanzado": {"days": 5, "exercises_per_day": 8}
    }

    # Mapeo de objetivos con grupos musculares y targets
    objective_mapping = {
        "Bajar de peso": {
            "body_parts": [
                ["cardio", "parte superior de las piernas", "cintura"],  # Día 1
                ["espalda", "cardio", "cintura"],                        # Día 2
                ["cardio", "parte superior de las piernas", "espalda"],  # Día 3
                ["cintura", "espalda"],                                  # Día 4
                ["cardio", "cintura"],                                   # Día 5
            ],
        },
        "Ganar masa muscular": {
            "body_parts": [
                ["pecho", "hombros"],                                    # Día 1
                ["parte superior de los brazos", "parte superior de las piernas"],  # Día 2
                ["espalda", "pecho"],                                    # Día 3
                ["hombros", "parte superior de los brazos"],             # Día 4
                ["parte superior de las piernas", "espalda"],            # Día 5
            ],
        },
        "Mantenerse en forma": {
            "body_parts": [
                ["cintura", "parte inferior de las piernas"],            # Día 1
                ["espalda", "brazos inferiores"],                        # Día 2
                ["hombros", "cintura"],                                  # Día 3
                ["brazos inferiores", "parte inferior de las piernas"],  # Día 4
                ["cintura", "espalda"],                                  # Día 5
            ],
        },
    }


    config = level_config[experience_level]
    body_parts_per_day = objective_mapping[objective]["body_parts"]

    try:

        routine = []
        for day, body_parts in enumerate(body_parts_per_day[:config["days"]], start=1):
        # Obtener ejercicios aleatorios para cada grupo muscular del día
            exercises = []
            for body_part in body_parts:
                exercises += conn.get_random_exercises(body_part, config["exercises_per_day"] // len(body_parts))
            routine.append({"day": day, "exercises": exercises})

        conn.save_routine(user_id, routine)     
        return {"message": "Rutina generada exitosamente", "routine": routine}
 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar la rutina: {str(e)}")
    
@app.get("/api/exercises/routine")
def get_user_routine(user_id: int = Query(..., description="ID del usuario")):
    try:     
        routine = conn.get_user_routine(user_id)
        if routine:
            return {
                "message": "Rutina encontrada",
                "routine": routine["routine"],
            }
        else:
            return {
                "message": "No se encontró una rutina para el usuario",
                "routine": None
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar la rutina: {str(e)}")
    
@app.put("/api/user/update-goals")
def update_user_goals(update: UpdateUserSchema):
    try:
        # Llamar al método para realizar el update
        success = conn.update_user_goals_in_db(
            update.usuario_id,
            update.objetivo,
            update.nivel_experiencia
        )

        if success:
            return {"message": "Objetivo y/o nivel actualizados exitosamente"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar los objetivos: {str(e)}")
    
@app.post("/api/progress")
def register_progress(progress: ProgressSchema):
    try:
        # Llamar al método para guardar el progreso
        success = conn.save_user_progress(
            progress.usuario_id,
            progress.ejercicio_id,
            progress.repeticiones,
            progress.peso
        )

        if success:
            return {"message": "Avance registrado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar el avance: {str(e)}")
    
@app.get("/api/progress/{usuario_id}")
def get_user_progress(usuario_id: int):
    try:
        # Llamar al método para obtener el progreso del usuario
        progress = conn.get_user_progress(usuario_id)

        if progress:
            return {"progress": progress}
        else:
            return {"progress": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener el progreso: {str(e)}")

@app.delete("/api/progress/{progress_id}")
def delete_user_progress(progress_id: int):
    try:
        success = conn.delete_user_progress(progress_id)
        if success:
            return {"message": "Registro eliminado exitosamente"}
        else:
            raise HTTPException(status_code=404, detail="Registro no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar el registro: {str(e)}")
    
@app.get("/api/exercises/body-parts")
def get_body_parts():
    try:
        body_parts = conn.get_unique_body_parts()
        return {"body_parts": body_parts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener body parts: {str(e)}")
    
@app.get("/api/exercises/by-body-part")
def get_exercises_by_body_part(
    body_part: str
):
    try:
        # Llamar al método para obtener los ejercicios
        exercises = conn.get_exercises_filtered(body_part)
        return {"exercises": exercises}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener ejercicios: {str(e)}")

@app.post("/api/nutrition-plan")
def obtener_plan_alimenticio(data: NutritionPlanRequest):
    try:
        # Cálculo de calorías
        calorias = conn.calcular_calorias(
            data.genero,
            data.edad,
            data.peso_actual,
            data.altura,
            data.nivel_experiencia,
            data.objetivo,
        )
        
        # Cálculo de macronutrientes
        macros = conn.calcular_macros(calorias, data.objetivo)

        # Generación de recomendaciones con Cohere
        prompt = f"""
        Genera un plan alimenticio para 4 días basado en los siguientes datos:
        - Género: {data.genero}
        - Edad: {data.edad}
        - Peso actual: {data.peso_actual} kg
        - Altura: {data.altura} cm
        - Nivel de experiencia: {data.nivel_experiencia}
        - Objetivo: {data.objetivo}
        - Calorías calculadas: {calorias} kcal
        - Macronutrientes (g): Proteínas: {macros["proteinas"]}, Carbohidratos: {macros["carbohidratos"]}, Grasas: {macros["grasas"]}

        Devuelve las recomendaciones en formato JSON con la siguiente estructura:
        {{
            "dia 1": {{
                "desayuno": "Descripción del desayuno",
                "almuerzo": "Descripción del almuerzo",
                "cena": "Descripción de la cena",
                "snack": "Descripción del snack"
            }},
            "dia 2": {{
                "desayuno": "...",
                "almuerzo": "...",
                "cena": "...",
                "snack": "..."
            }},
            "dia 3": {{
                ...
            }},
            "dia 4": {{
                ...
            }}
        }}
        No incluyas explicaciones ni introducciones, solo responde en formato JSON.
        """
        
        # Llamada al modelo de Cohere
        response = co.chat(
            model="command-r-plus",
            message=prompt
        )

        # Extraer la respuesta de Cohere
        if hasattr(response, 'text'):
            raw_recommendations = response.text
        elif hasattr(response, 'reply'):
            raw_recommendations = response.reply
        else:
            raise AttributeError("No se encontró un atributo adecuado en la respuesta de Cohere")
        
        # Convertir la respuesta a JSON limpio
        try:
            recommendations = json.loads(raw_recommendations)  # Decodifica la cadena JSON a un objeto
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="La IA no devolvió un JSON válido. Revisa el prompt o los datos.")
        
        for day, meals in recommendations.items():
            for meal, description in meals.items():
                recommendations[day][meal] = description.replace('\n', ' ')

        conn.insert_recommendations(data.id_usuario, recommendations)

        return {
            "calorias": calorias,
            "macros": macros,
            "recomendaciones": recommendations,  # Devuelve un JSON limpio
        }

    except AttributeError as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la solicitud con Cohere: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar plan: {str(e)}")
    
@app.get("/api/recommendations/daily")
def get_daily_recommendations(
    user_id: int = Query(..., description="ID del usuario"),):
    try:
        result = conn.fetch_recommendations(user_id)

        if result:
            return {
                "message": "Recomendaciones encontradas",
                "recommendations": result["recomendaciones"],
            }
        else:
            return {
                "message": "No se encontraron recomendaciones para el usuario",
                "recommendations": None,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar las recomendaciones: {str(e)}")