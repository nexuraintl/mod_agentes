import os
import json
import logging
import datetime
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from services.update_service import ZnunyService

# Configure logging for the controller
logger = logging.getLogger(__name__)

router = APIRouter()

# Instantiate the service (Singleton pattern for this module)
znuny_service = ZnunyService()

# --------------------------------------------------------------------------
## Endpoint: Webhook de Znuny (/znuny-webhook)
# --------------------------------------------------------------------------
@router.api_route("/znuny-webhook", methods=["POST", "GET", "PUT"])
async def znuny_webhook(request: Request):
    """Recibe webhooks desde Znuny y procesa el diagnóstico del ticket."""
    
    # Obtener el cuerpo de la petición
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")
    
    # Payload para logging (Siguiendo tu lógica original)
    payload_json = {}
    try:
        payload_json = await request.json()
    except:
        payload_json = {}

    # Estructura de log compatible con tu histórico
    log_entry = {
        "time": datetime.datetime.utcnow().isoformat() + "Z",
        "method": request.method,
        "headers": dict(request.headers),
        "json": payload_json,
        "raw_body": body_str,
    }

    # Guardado de Logs (Se mantiene lógica de archivos para soporte actual)
    # Nota: En Cloud Run esto es volátil, idealmente usar Cloud Logging.
    logs_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "znuny_requests.log")
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n\n")
    except Exception as e:
        logger.error(f"Failed to write to log file: {e}")

    # Búsqueda de TicketID (Lógica robusta del manual) 
    ticket_id = (
        (payload_json.get("Event") or {}).get("TicketID")
        or (payload_json.get("Ticket") or {}).get("TicketID")
        or payload_json.get("TicketID")
    )

    if not ticket_id:
        logger.error("No TicketID found in payload")
        raise HTTPException(status_code=400, detail="No se encontró TicketID en el payload")

    # Gestión de Sesión y Diagnóstico
    try:
        session_id = znuny_service.get_or_create_session_id()
        logger.info(f"[Webhook] Processing ticket {ticket_id}...")
        
        # Ejecutar lógica central
        result = znuny_service.diagnose_and_update_ticket(
            ticket_id=ticket_id,
            session_id=session_id,
            data=payload_json
        )
        
        # Manejo de tickets omitidos (Filtro de estados) [cite: 130]
        if isinstance(result, dict) and result.get("skipped"):
            return {
                "status": "skipped",
                "ticket_id": ticket_id, 
                "reason": result.get("reason")
            }

        return {"status": "ok", "ticket_id": ticket_id}

    except Exception as e:
        logger.error(f"[Webhook] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fallo en la actualización: {str(e)}")