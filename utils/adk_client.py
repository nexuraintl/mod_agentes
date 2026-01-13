from google import genai
from google.genai import types
import os

class ADKClient:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")
        self.client = genai.Client(api_key=api_key)

    def diagnose_ticket(self, ticket_text, tool_config=None):
        try:
            # ----------------------------------------------------------------------
            # 1. CONTEXTO Y PROMPT (MODIFICADO: RAG ENABLED)
            # ----------------------------------------------------------------------
            prompt = f"""
Eres un ingeniero de soporte de nivel 1 especializado en diagnosticar y clasificar tickets.

# INSTRUCCIONES DE ANÁLISIS

1. Analiza el ticket recibido.
2. **CONSULTA TU BASE DE CONOCIMIENTO** (usando las herramientas disponibles) para buscar casos similares, soluciones previas o documentación relevante.
3. Identifica la intención (Incidente, Petición, Requerimiento).
4. Genera un diagnóstico técnico basado en la evidencia del ticket y la información recuperada.

# TABLA DE CLASIFICACIÓN (OBLIGATORIA)
Tipo | ID Znuny | Descripción | Acción Inicial
-----|-----------|--------------|----------------
Incidente | 10 | Falla, interrupción o degradación | Replicar, escalar con causa raíz.
Petición | 14 | Solicitud de acción sobre existente | Resolver o escalar.
Requerimiento | 19 | Solicitud de nueva funcionalidad | Escalar a desarrollo.

# FORMATO DE SALIDA (ESTRICTO JSON)

{{
  "type_id": 10|14|19,
  "diagnostico": "Texto del diagnóstico..."
}}

# REGLAS
- Usa la información recuperada para enriquecer el diagnóstico.
- Si no encuentras información relevante en la base de conocimiento, usa tu criterio general.
- Respuesta SOLO en JSON.

TICKET A ANALIZAR:
{ticket_text}
"""
            # ----------------------------------------------------------------------
            # 2. LLAMADA A LA API CON TOOLS
            # ----------------------------------------------------------------------
            
            # Configuración de herramientas
            tools = []
            if tool_config:
                # Asumimos que tool_config es una lista de herramientas o un objeto Tool válido
                if isinstance(tool_config, list):
                    tools.extend(tool_config)
                else:
                    tools.append(tool_config)

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig( 
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    temperature=0.2,
                    tools=tools # Inyectamos las herramientas (RAG)
                )
            )
            print("🔍 Respuesta cruda:", response)
            return response.text
                

        except Exception as e:
            print(f" Error en diagnose_ticket: {e}")
            return ""

    def extract_client(self, metadata: dict, article_text: str) -> dict:
        """
        Extrae la información del cliente/entidad real afectada del ticket.
        Solo se usa para tickets clasificados como Incidentes.
        """
        try:
            import json
            
            prompt = f"""
Eres un analista especializado en identificar clientes y entidades en tickets de soporte.

# TAREA
Analiza el ticket de soporte e identifica:
1. La entidad/empresa/cliente REAL que tiene el problema (NO el usuario interno que creó el ticket)
2. El contacto del cliente si está disponible en el texto
3. El email del contacto si está disponible
4. Un resumen breve del problema (máximo 50 palabras)

# METADATA DEL TICKET
{json.dumps(metadata, ensure_ascii=False, indent=2)}

# CONTENIDO DEL TICKET
{article_text}

# FORMATO DE SALIDA (ESTRICTO JSON)
{{
  "entidad": "nombre de la empresa/entidad afectada o 'No identificado'",
  "contacto": "nombre del contacto o null",
  "email": "email del contacto o null",
  "problema_resumido": "resumen breve del problema",
  "confianza": 0.0 a 1.0
}}

# REGLAS
- Si no puedes identificar la entidad real, usa "No identificado"
- El customer_id o customer_user de la metadata NO es el cliente real, es el usuario interno
- Busca en el contenido del ticket menciones a empresas, alcaldías, instituciones, etc.
- Respuesta SOLO en JSON válido.
"""
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    temperature=0.1
                )
            )
            
            # Parse response
            response_text = response.text.strip()
            # Clean markdown if present
            if response_text.startswith("```"):
                response_text = response_text.strip("`").replace("json", "").strip()
            
            return json.loads(response_text)
            
        except Exception as e:
            print(f"❌ Error en extract_client: {e}")
            return {
                "entidad": "Error en extracción",
                "contacto": None,
                "email": None,
                "problema_resumido": str(e),
                "confianza": 0.0
            }