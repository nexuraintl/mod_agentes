# services/agent_service.py

from utils.adk_client import ADKClient
import json
import logging
from typing import Union, Dict, Optional

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        self.adk_client = ADKClient()

    def diagnose_ticket(self, ticket_text: str, examples_context: str = "") -> Union[str, Dict[str, Optional[str]]]:
        """
        Calls the model, receives a JSON string, parses it, and returns the formatted
        diagnosis text for the Znuny article.
        """
        response_text = self.adk_client.diagnose_ticket(ticket_text, examples_context)
        
        if not response_text:
            logger.warning("Automatic diagnosis unavailable (AI Model did not respond).")
            return "Diagnóstico automático no disponible (Modelo de IA no respondió)."

        # Try to parse the JSON returned by the IA
        try:
            # Sometimes the IA returns JSON wrapped in markdown code blocks
            cleaned = response_text.strip().strip("`").replace("json", "")
            data = json.loads(cleaned)
            diagnostico = data.get("diagnostico") or data.get("diagnosis")
            type_id = data.get("type_id")

            if not diagnostico:
                logger.warning("Automatic diagnosis unavailable (AI returned empty diagnosis field).")
                return "Diagnóstico automático no disponible (IA no entregó campo diagnóstico)."

            return {
                "type_id": type_id,
                "diagnostico": diagnostico or "Diagnóstico no disponible (IA vacía)."
            }

        except json.JSONDecodeError:
            # If not JSON, return text only
            logger.info("AI response was not JSON, returning raw text.")
            return {"diagnostico": response_text.strip(), "type_id": None}