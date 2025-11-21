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