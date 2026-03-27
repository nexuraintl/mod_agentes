from google import genai
from google.genai import types
import os
import json
import logging

# Configuración de logger para Cloud Run
logger = logging.getLogger(__name__)

class ADKClient:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")
        self.client = genai.Client(api_key=api_key)

    def diagnose_ticket(self, ticket_text, tool_config=None):
        """
        Diagnostica y clasifica el ticket utilizando RAG y lógica de soporte avanzada.
        """
        try:
            # 1. PROMPT OPTIMIZADO: Foco en discriminación Lógica vs Visual
            prompt = f"""
Eres un Ingeniero de Soporte Nivel 1 Senior en Nexura. Tu objetivo es realizar un triaje técnico preciso.

# INSTRUCCIONES DE ANÁLISIS
1. **RAG (Knowledge Base)**: Consulta obligatoriamente tu base de conocimiento para buscar soluciones o contextos previos de Nexura.
2. **Clasificación**: Identifica si es Incidente (10), Petición (14) o Requerimiento (19).
3. **Seguridad**: Evalúa si hay brechas, ataques o riesgos de datos (is_security_alert).
4. **Análisis Visual (Discriminación Crítica)**:
   - Marca `requires_visual=true` SOLO si la falla es estética/gráfica (colores, fuentes, imágenes rotas, desalineación CSS).
   - Marca `requires_visual=false` si el cambio es de lógica, aunque sea en un formulario (ej: hacer campo obligatorio, cambiar tipo de input, validación de cédula, horarios).

# TABLA DE CLASIFICACIÓN
- Incidente (10): Error, caída de servicio o mal funcionamiento de algo existente.
- Petición (14): Configuración, creación de usuarios o dudas sobre el uso.
- Requerimiento (19): Nuevas funciones, cambios en reglas de negocio o lógica de validación.

# REGLAS DE ORO
- **Diagnóstico**: No entregues código JSON crudo de la base de conocimiento. Explica la solución de forma técnica pero legible.
- **Seguridad**: Si se menciona Ransomware o acceso no autorizado, criticality_score = 10 y is_security_alert = true.
- **Formato**: Responde EXCLUSIVAMENTE en JSON.

TICKET A ANALIZAR:
{ticket_text}

# FORMATO DE SALIDA (JSON)
{{
  "type_id": 10|14|19,
  "criticality_score": 1-10,
  "is_security_alert": true|false,
  "requires_visual": true|false,
  "diagnostico": "Tu explicación aquí..."
}}
"""
            # Configuración de herramientas (RAG)
            tools = []
            if tool_config:
                if isinstance(tool_config, list): tools.extend(tool_config)
                else: tools.append(tool_config)

            # Usamos gemini-2.0-flash (la versión 2.5 no es estándar, 2.0 es la recomendada para RAG)
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig( 
                    temperature=0.2, # Baja para mantener consistencia en el JSON
                    tools=tools
                )
            )
            
            # Limpieza y validación de la respuesta
            res_text = response.text.strip()
            if res_text.startswith("```"):
                res_text = res_text.strip("`").replace("json", "").strip()
            
            return res_text

        except Exception as e:
            logger.error(f"Error en diagnose_ticket: {e}")
            return json.dumps({
                "type_id": 14,
                "criticality_score": 3,
                "is_security_alert": False,
                "requires_visual": False,
                "diagnostico": f"Error procesando diagnóstico: {str(e)}"
            })

    def extract_client(self, metadata: dict, article_text: str) -> dict:
        """
        Identifica la entidad real afectada (Alcaldía, Gobernación, etc.)
        """
        try:
            prompt = f"""
Analiza el ticket e identifica la entidad real afectada.
Nota: El 'customer_id' suele ser genérico. Busca nombres de instituciones en el texto.

METADATA: {json.dumps(metadata, ensure_ascii=False)}
CONTENIDO: {article_text}

# FORMATO DE SALIDA (JSON)
{{
  "entidad": "Nombre de la empresa/entidad o 'No identificado'",
  "contacto": "Nombre de la persona",
  "email": "Email de contacto",
  "problema_resumido": "Resumen técnico (max 50 palabras)",
  "confianza": 0.0 a 1.0
}}
"""
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            
            res_text = response.text.strip()
            if res_text.startswith("```"):
                res_text = res_text.strip("`").replace("json", "").strip()
            
            return json.loads(res_text)
            
        except Exception as e:
            logger.error(f"Error en extract_client: {e}")
            return {"entidad": "No identificado", "problema_resumido": str(e), "confianza": 0.0}