import json
import psycopg
import pickle
import numpy as np


class UserConnection():
    conn = None

    def __init__(self):
        try:
            self.conn = psycopg.connect("dbname=gym user=postgres password=password host=localhost port=5432")
        except psycopg.OperationalError as err:
            print(err)
            self.conn.close()

    def write(self, data):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO "usuarios"(nombre, apellido, email, password_hash) VALUES(%(nombre)s, %(apellido)s, %(email)s, %(password_hash)s)
            """, data)
            self.conn.commit()

    def get_user_by_email(self, email: str):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, nombre, apellido, email, password_hash, datos_completos FROM "usuarios" WHERE email = %s
            """, (email,))
            result = cur.fetchone()

            if result:
                return {
                    "id": result[0],
                    "nombre": result[1],
                    "apellido": result[2],
                    "email": result[3],
                    "password_hash": result[4],
                    "datos_completos": result[5]
                }
            return None

    def get_user_by_id(self, user_id: int):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT nombre, apellido, email, genero, edad, altura, peso_actual, objetivo, nivel_experiencia
                FROM "usuarios" 
                WHERE id = %s
            """, (user_id,))
            result = cur.fetchone()

            if result:
                return {
                    "nombre": result[0],
                    "apellido": result[1],
                    "email": result[2],
                    "genero": result[3],
                    "edad": result[4],
                    "altura": result[5],
                    "peso_actual": result[6],
                    "objetivo": result[7],
                    "nivel_experiencia": result[8]
                }
            return None
        
    def update_user(self, user_id: int, updated_data: dict):
        update_fields = {key: value for key, value in updated_data.items() if value is not None}
        if not update_fields:
            raise ValueError("No hay datos para actualizar.")

        # Validar vector biométrico antes de procesarlo
        if "vector_biometrico" in update_fields:
            vector_biometrico = updated_data["vector_biometrico"]

            # Si el vector ya está en bytes
            if isinstance(vector_biometrico, bytes):
                update_fields["vector_biometrico"] = vector_biometrico
            # Si el vector es un numpy array (no debería llegar como tal, pero por si acaso)
            elif isinstance(vector_biometrico, np.ndarray):
                if vector_biometrico.shape[0] != 128:
                    raise ValueError(f"El vector biométrico tiene un tamaño inválido: {vector_biometrico.shape[0]}.")
                update_fields["vector_biometrico"] = vector_biometrico.tobytes()
            else:
                raise ValueError("El vector biométrico tiene un formato desconocido.")
            
        # Crear la consulta SQL dinámica
        set_clause = ", ".join([f"{key} = %({key})s" for key in update_fields])
        
        query = f"""
            UPDATE "usuarios" SET {set_clause} WHERE id = %(user_id)s
        """
        update_fields["user_id"] = user_id

        with self.conn.cursor() as cur:
            cur.execute(query, update_fields)
            self.conn.commit()

        return True
    

    def get_trainers_by_specialty(self, specialty: str = None):
        # Consulta base para obtener entrenadores activos
        query = """
            SELECT 
                e.id_entrenador, 
                e.nombre, 
                e.especialidad, 
                c.nombre_clase,
                h.id_horario, 
                h.dia_semana
            FROM entrenadores e
            INNER JOIN clases c ON c.id_entrenador = e.id_entrenador
            INNER JOIN horario h ON h.id_clase = c.id_clase
            WHERE e.estado = true
        """
        params = []

        # Agregar filtro opcional por especialidad
        if specialty:
            query += " AND e.especialidad = %s"
            params.append(specialty)

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchall()

        # Mapear los resultados a un formato de diccionario
        return [
            {
                "id_entrenador": row[0],
                "nombre": row[1],
                "especialidad": row[2],
                "nombre_clase": row[3],
                "id_horario": row[4],
                "dia_semana": row[5],
            }
            for row in result
        ]
    

    def get_class_details_by_schedule(self, id_horario: int):
        query = """
            SELECT  
                e.nombre, 
                e.descripcion, 
                e.telefono,
                e.correo,
                c.nombre_clase,
                c.descripcion AS descripcion_clase,
                c.nivel,
                h.dia_semana,
                TO_CHAR(h.hora_inicio, 'HH24:MI') AS hora_inicio,
                TO_CHAR(h.hora_fin, 'HH24:MI') AS hora_fin
            FROM entrenadores e
            INNER JOIN clases c ON c.id_entrenador = e.id_entrenador
            INNER JOIN horario h ON h.id_clase = c.id_clase
            WHERE h.id_horario = %s
        """
        params = [id_horario]

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchone()

        if not result:
            return None

        return {
            "nombre": result[0],
            "descripcion": result[1],
            "telefono": result[2],
            "correo": result[3],
            "nombre_clase": result[4],
            "descripcion_clase": result[5],
            "nivel": result[6],
            "dia_semana": result[7],
            "hora_inicio": result[8],
            "hora_fin": result[9],
        }
    
    def get_random_exercises(self, body_part, limit):
        query = """
                SELECT id, name_es, body_part_es, target_es
                FROM ejercicios
                WHERE body_part_es = %s
                ORDER BY RANDOM()
                LIMIT %s
            """
        with self.conn.cursor() as cur:
            cur.execute(query, (body_part, limit)) 
            result = cur.fetchall()

        return [
            {"id": row[0], "name_es": row[1], "body_part_es": row[2], "target_es": row[3]}
            for row in result
        ]
    

    def save_routine(self, user_id, routine):
        query = """
            INSERT INTO usuario_rutinas (usuario_id, rutina)
            VALUES (%s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (user_id, json.dumps(routine)))
            self.conn.commit()

    def get_user_routine(self, user_id):
        query = """
            SELECT rutina
            FROM usuario_rutinas
            WHERE usuario_id = %s
            ORDER BY fecha_creacion DESC
            LIMIT 1
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (user_id,))
            result = cur.fetchone()

        if result:
            return {
                "routine": result[0],  # Contenido JSON de la rutina
            }
        else:
            return None
        
    def update_user_goals_in_db(self, usuario_id, objetivo=None, nivel_experiencia=None):
        query = """
            UPDATE usuarios
            SET objetivo = COALESCE(%s, objetivo),
                nivel_experiencia = COALESCE(%s, nivel_experiencia)
            WHERE id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (objetivo, nivel_experiencia, usuario_id))
            self.conn.commit()
        return True
    
    def save_user_progress(self, user_id, exercise_id, reps, weight=None):
        query = """
            INSERT INTO usuario_avances (usuario_id, ejercicio_id, repeticiones, peso)
            VALUES (%s, %s, %s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (user_id, exercise_id, reps, weight))
            self.conn.commit()
        return True
    

    def get_user_progress(self, user_id):
        query = """
            SELECT
                u.id, 
                u.repeticiones, 
                u.peso, 
                u.fecha, 
                e.name_es
            FROM usuario_avances u
            INNER JOIN ejercicios e ON e.id = u.ejercicio_id
            WHERE u.usuario_id = %s
            ORDER BY u.fecha DESC
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (user_id,))
            results = cur.fetchall()

        if results:
            return [
                {
                    "id": row[0],
                    "repeticiones": row[1],
                    "peso": row[2],
                    "fecha": row[3].strftime('%d-%m-%Y'),
                    "name_es": row[4]
                }
                for row in results
            ]
        else:
            return []

    def delete_user_progress(self, progress_id: int) -> bool:
        query = "DELETE FROM usuario_avances WHERE id = %s"
        with self.conn.cursor() as cur:
            cur.execute(query, (progress_id,))
            self.conn.commit()
            # Verificar si se eliminó alguna fila
            return cur.rowcount > 0
        

    def get_unique_body_parts(self):
        query = """
            SELECT body_part_es
            FROM ejercicios
            GROUP BY body_part_es
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            raise Exception(f"Error al obtener body parts: {str(e)}")
        
    def get_exercises_filtered(self, body_part: str):
        sql = """
            SELECT id, name_es
            FROM ejercicios
            WHERE body_part_es = %s
        """
        params = [body_part]

        try:
            # Ejecutar consulta
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                results = cur.fetchall()
            return [{"id": row[0], "name_es": row[1]} for row in results]
        except Exception as e:
            raise Exception(f"Error al obtener ejercicios: {str(e)}")

    def __def__(self):
        self.conn.close()