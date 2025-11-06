# services/agent_service.py

from utils.adk_client import ADKClient
import json # Necesitamos la librería json para parsear
import os
import time
import requests


class AgentService:
    def __init__(self):
        self.adk_client = ADKClient()

    def diagnose_ticket(self, ticket_text: str) -> str:
        """
        Llama al modelo, recibe una cadena JSON, la parsea y retorna el texto
        de diagnóstico formateado para el artículo de Znuny.
        """
        response_text = self.adk_client.diagnose_ticket(ticket_text)
        
        if not response_text:
            return "Diagnóstico automático no disponible (Modelo de IA no respondió)."

        # Intentar parsear el JSON que devuelve la IA
        try:
            # A veces la IA devuelve el JSON entre json ... 
            cleaned = response_text.strip().strip("`").replace("json", "")
            data = json.loads(cleaned)
            diagnostico = data.get("diagnostico") or data.get("diagnosis")
            type_id = data.get("type_id")

            if not diagnostico:
                return "Diagnóstico automático no disponible (IA no entregó campo diagnóstico)."

            return {
                "type_id": type_id,
                "diagnostico": diagnostico or "Diagnóstico no disponible (IA vacía)."
            }

        except json.JSONDecodeError:
            # Si no es JSON, devolvemos solo texto
            return {"diagnostico": response_text.strip(), "type_id": None}