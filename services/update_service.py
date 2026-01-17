import os
import json
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, Union
from .agent_service import AgentService
from .knowledge_base_service import KnowledgeBaseService

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ZnunyService:
    """
    Service to interact with Znuny API, handling authentication,
    ticket retrieval, and updates.
    """

    def __init__(self):
        self.base_url = os.environ.get("ZNUNY_BASE_API", "").rstrip("/")
        self.username = os.environ.get("ZNUNY_USERNAME")
        self.password = os.environ.get("ZNUNY_PASSWORD")
        self.session_ttl = int(os.environ.get("ZNUNY_SESSION_TTL", "3300"))
        
        self._cached_session_id: Optional[str] = None
        self._cached_session_ts: float = 0.0
        
        # Lazy initialization of AgentService to avoid import errors at module level
        self._agent_service: Optional[AgentService] = None
        self._kb_service: Optional[KnowledgeBaseService] = None
        
        # ThreadPoolExecutor for async incident processing
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="incident_")

    @property
    def kb_service(self) -> KnowledgeBaseService:
        if self._kb_service is None:
            self._kb_service = KnowledgeBaseService()
        return self._kb_service

    @property
    def agent_service(self) -> AgentService:
        if self._agent_service is None:
            try:
                self._agent_service = AgentService()
            except ImportError as e:
                logger.error(f"Failed to load AgentService: {e}")
                raise RuntimeError(f"Failed to load AgentService: {e}")
        return self._agent_service

    def _login_create_session(self) -> str:
        """Creates a new SessionID by authenticating against Znuny."""
        if not all([self.username, self.password, self.base_url]):
            raise ValueError("Missing required environment variables: ZNUNY_USERNAME, ZNUNY_PASSWORD, or ZNUNY_BASE_API")

        url = f"{self.base_url}/Session"
        payload = {"UserLogin": self.username, "Password": self.password}
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "mod_agentes/1.0",
        }

        try:
            resp = requests.patch(
                url,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            session_id = data.get("SessionID")
            if not session_id:
                raise RuntimeError(f"Znuny did not return SessionID. Response: {data}")

            return session_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection error during authentication: {e}")
            raise RuntimeError(f"Connection error during authentication: {e}")

    def get_or_create_session_id(self) -> str:
        """Retrieves or generates a valid SessionID, using memory cache."""
        # Check environment variable override
        env_sid = os.environ.get("ZNUNY_SESSION_ID") or os.environ.get("SESSION_ID")
        if env_sid:
            return env_sid

        now = time.time()
        if self._cached_session_id and (now - self._cached_session_ts) < self.session_ttl:
            return self._cached_session_id

        logger.info("Creating new Znuny session...")
        self._cached_session_id = self._login_create_session()
        self._cached_session_ts = now
        return self._cached_session_id

    def get_ticket_metadata(self, ticket_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene la metadata completa de un ticket, incluyendo cliente.
        """
        url = f"{self.base_url}/Ticket/{ticket_id}?SessionID={session_id}"
        
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            ticket = data.get("Ticket")
            if isinstance(ticket, list):
                ticket = ticket[0]
            
            return {
                "ticket_id": ticket.get("TicketID"),
                "ticket_number": ticket.get("TicketNumber"),
                "title": ticket.get("Title"),
                "customer_id": ticket.get("CustomerID"),        # Empresa
                "customer_user": ticket.get("CustomerUserID"),  # Usuario
                "queue": ticket.get("Queue"),
                "state": ticket.get("State"),
                "priority": ticket.get("Priority"),
                "owner": ticket.get("Owner"),
                "type": ticket.get("Type"),
                "created": ticket.get("Created"),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get metadata for ticket {ticket_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting ticket metadata: {e}")
            return None

    def get_ticket_latest_article(self, ticket_id: int, session_id: str) -> Optional[str]:
        """
        Retrieves the text of the most relevant article from a Znuny ticket.
        """
        headers = {"Accept": "application/json"}
        url_ticket = f"{self.base_url}/Ticket/{ticket_id}?SessionID={session_id}&AllArticles=1"

        try:
            r = requests.get(url_ticket, headers=headers, timeout=10)
            r.raise_for_status() 
            data = r.json()
            
            ticket_data = data.get("Ticket")
            if isinstance(ticket_data, list):
                ticket_data = ticket_data[0]
                
            articles = ticket_data.get("Article") if ticket_data else None
            return self._extract_relevant_text(articles)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get article for ticket {ticket_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing Znuny articles: {e}")
            return None

    def _extract_relevant_text(self, articles: list) -> Optional[str]:
        """Helper to extract text from a list of articles."""
        if not isinstance(articles, list) or not articles:
            return None

        # Sort by CreateTime or ArticleID
        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("CreateTime") or a.get("ArticleID") or 0
        )
        
        if not sorted_articles:
            return None
            
        # Logic: Take the FIRST article (the inception of the ticket), as it contains the user's original request.
        # This avoids picking up system notifications or auto-replies added later.
        last_relevant = sorted_articles[0]
        
        subject = last_relevant.get("Subject", "")
        body = last_relevant.get("Body", "")
        
        if not subject and not body:
            return None
        
        return f"Subject: {subject}\n---\nBody:\n{body}"

    def update_ticket(self, ticket_id: int, session_id: str, title: str, user: str, 
                     queue_id: int, priority_id: int, state_id: int, 
                     subject: str, body: str, dynamic_fields: Optional[dict] = None, 
                     type_id: Optional[int] = None) -> Dict[str, Any]:
        """Updates a ticket in Znuny adding a new article and metadata."""
        
        url = f"{self.base_url}/Ticket/{ticket_id}"
        payload = {
            "SessionID": session_id,
            "TicketID": ticket_id,
            "Ticket": {
                "Title": title,
                "CustomerUser": user,
                "QueueID": queue_id,
                "TypeID": type_id,
                "PriorityID": priority_id,
                "StateID": state_id
            },
            "Article": {
                "Subject": subject,
                "Body": body,
                "ContentType": "text/plain; charset=utf8"
            }
        }

        if dynamic_fields:
            payload["Ticket"]["DynamicFields"] = dynamic_fields
            
        if type_id is not None:
            payload["Ticket"]["TypeID"] = type_id
        
        logger.debug(f"Sending update payload to Znuny: {json.dumps(payload, indent=2, ensure_ascii=False)}")

        try:
            r = requests.patch(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update Znuny ticket {ticket_id}: {e}")
            return {"error": str(e)}

    # =========================================================================
    # PRIVATE HELPERS (Single Responsibility Principle)
    # =========================================================================
    
    def _get_rag_tool_config(self):
        """Gets the RAG tool configuration. Returns None if unavailable."""
        try:
            store_name = self.kb_service.get_or_create_store(display_name="Znuny_Tickets_KB")
            if store_name:
                tool_config = self.kb_service.get_tool_config(store_name)
                logger.info(f"✅ RAG Tool Configured with Store: {store_name}")
                return tool_config
            logger.warning("⚠️ Failed to get Store Name for RAG.")
            return None
        except Exception as e:
            logger.error(f"❌ Error configuring RAG: {e}")
            return None

    def _generate_diagnosis(self, ticket_text: str, tool_config) -> Dict[str, Any]:
        """
        Generates AI diagnosis from ticket text.
        Returns dict with 'type_id', 'requires_visual', and 'diagnostico'.
        """
        response_data = self.agent_service.diagnose_ticket(ticket_text, tool_config)
        
        if isinstance(response_data, str):
            return {"type_id": None, "requires_visual": False, "diagnostico": response_data}
        
        return {
            "type_id": response_data.get("type_id"),
            "requires_visual": response_data.get("requires_visual", False),
            "diagnostico": response_data.get("diagnostico")
        }


    def _process_incident(self, ticket_id: int, session_id: str, 
                          ticket_text: str, diagnosis_body: str, 
                          type_id: int) -> Optional[dict]:
        """
        Processes incident tickets (type_id=10).
        Extracts client info and delegates to error_log in a separate thread.
        Returns incident_data with delegated=True immediately.
        """
        if type_id != 10:
            return None
            
        logger.info("🔍 Ticket is INCIDENT - Extracting real client info...")
        
        try:
            metadata = self.get_ticket_metadata(ticket_id, session_id)
            if not metadata:
                logger.warning("Could not get ticket metadata for incident processing")
                return None
            
            # Extract client using AI
            client_info = self.agent_service.extract_client_info(metadata, ticket_text)
            entity = client_info.get('entidad', 'No identificado')
            
            logger.info(f"📍 Cliente real detectado: {entity}")
            
            # Build incident data for async processing
            import datetime
            incident_data = {
                "ticket_id": str(ticket_id),
                "ticket_number": metadata.get("ticket_number"),
                "title": metadata.get("title", ""),
                "ticket_text": ticket_text,
                "entity": entity,
                "diagnostico_inicial": diagnosis_body,
                "session_id": session_id,
                "queue_id": 1,
                "priority_id": 3,
                "state_id": 4,
                "processed_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
            
            # Launch async processing in separate thread
            self._executor.submit(
                self._process_incident_async,
                incident_data
            )
            logger.info(f"🚀 Incident {ticket_id} delegated to background thread for error_log processing")
            
            # Return with delegated flag
            incident_data["delegated"] = True
            return incident_data
            
        except Exception as e:
            logger.error(f"❌ Error processing incident data: {e}")
            return None

    def _process_incident_async(self, incident_data: dict) -> None:
        """
        Async handler that runs in a separate thread.
        Calls error_log, waits for response, formats as text, updates Znuny.
        """
        ticket_id = incident_data["ticket_id"]
        entity = incident_data["entity"]
        session_id = incident_data["session_id"]
        
        logger.info(f"� [Thread] Starting async processing for ticket {ticket_id}, entity: {entity}")
        
        try:
            # 1. Call error_log and wait for response
            error_log_response = self._call_error_log(incident_data)
            
            if not error_log_response:
                logger.warning(f"⚠️ [Thread] No response from error_log for ticket {ticket_id}")
                # Update Znuny with fallback message
                fallback_body = self._format_no_logs_found(entity, incident_data.get("diagnostico_inicial", ""))
                self._update_znuny_article(
                    ticket_id=int(ticket_id),
                    session_id=session_id,
                    subject="Diagnóstico de Incidente (Sin logs encontrados)",
                    body=fallback_body,
                    type_id=10
                )
                return
            
            # 2. Format response as readable text
            formatted_body = self._format_error_log_response(entity, error_log_response)
            
            # 3. Update Znuny with formatted response
            self._update_znuny_article(
                ticket_id=int(ticket_id),
                session_id=session_id,
                subject="Diagnóstico de Incidente (Error Log)",
                body=formatted_body,
                type_id=10
            )
            
            logger.info(f"✅ [Thread] Ticket {ticket_id} updated with error_log diagnosis")
            
        except Exception as e:
            logger.error(f"❌ [Thread] Error in async incident processing for {ticket_id}: {e}")

    def _call_error_log(self, incident_data: dict) -> Optional[dict]:
        """
        Calls error_log /analyze-incident endpoint and waits for response.
        Returns parsed JSON response or None on failure.
        """
        log_monitor_url = os.environ.get("LOG_MONITOR_URL")
        if not log_monitor_url:
            logger.warning("⚠️ LOG_MONITOR_URL not configured - skipping error_log call")
            return None
        
        endpoint = f"{log_monitor_url}/analyze-incident"
        
        # Build payload matching error_log's DatosIncidente model
        payload = {
            "ticket_id": incident_data["ticket_id"],
            "ticket_number": incident_data.get("ticket_number"),
            "title": incident_data["title"],
            "ticket_text": incident_data["ticket_text"],
            "entity": incident_data["entity"],
            "diagnostico_inicial": incident_data.get("diagnostico_inicial")
        }
        
        try:
            logger.info(f"📤 [Thread] Calling error_log for entity: {incident_data['entity']}")
            response = requests.post(
                endpoint,
                json=payload,
                timeout=300  # 5 minutes - error_log may take time processing SSH logs
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"� [Thread] error_log response received: {data.get('logs_encontrados', 0)} logs found")
            return data
            
        except requests.exceptions.Timeout:
            logger.warning("⚠️ [Thread] error_log request timed out (5 min)")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ [Thread] Could not connect to error_log service")
            return None
        except Exception as e:
            logger.warning(f"⚠️ [Thread] Error calling error_log: {e}")
            return None

    def _format_error_log_response(self, entity: str, response: dict) -> str:
        """
        Formats error_log JSON response as readable text for Znuny.
        """
        logs_count = response.get("logs_encontrados", 0)
        diagnosticos = response.get("diagnosticos", [])
        resumen = response.get("mensaje_resumen", "")
        
        lines = [
            "[Procesado por: Error Log Monitor]",
            "",
            "═" * 55,
            f"DIAGNÓSTICO DE INCIDENTE - {entity}",
            "═" * 55,
            "",
            f"[INFO] Se encontraron {logs_count} errores fatales en las ultimas 2 horas.",
            ""
        ]
        
        # Add individual diagnostics (limit to 5)
        for i, diag in enumerate(diagnosticos[:5], 1):
            log_info = diag.get("log", {})
            diag_info = diag.get("diagnostico", {})
            
            lines.append(f"─── Error {i} ───")
            lines.append(f"Tipo: {diag_info.get('tipo_error', 'Desconocido')}")
            lines.append(f"Severidad: {diag_info.get('severidad', 'N/A')}")
            lines.append(f"Mensaje: {log_info.get('mensaje', 'N/A')[:200]}")
            lines.append(f"Diagnóstico: {diag_info.get('resumen', 'N/A')}")
            lines.append(f"Recomendación: {diag_info.get('recomendacion', 'N/A')}")
            lines.append("")
        
        if len(diagnosticos) > 5:
            lines.append(f"... y {len(diagnosticos) - 5} errores adicionales.")
            lines.append("")
        
        lines.extend([
            "═" * 55,
            "RESUMEN Y PRÓXIMOS PASOS",
            "═" * 55,
            resumen
        ])
        
        return "\n".join(lines)

    def _format_no_logs_found(self, entity: str, diagnostico_inicial: str) -> str:
        """
        Formats fallback message when no logs are found in error_log.
        """
        return f"""[Procesado por: Error Log Monitor]

═══════════════════════════════════════════════════════
DIAGNÓSTICO DE INCIDENTE - {entity}
═══════════════════════════════════════════════════════

[INFO] No se encontraron errores fatales relacionados con '{entity}' en las ultimas 2 horas.

─── Diagnóstico Inicial ───
{diagnostico_inicial}

═══════════════════════════════════════════════════════
PRÓXIMOS PASOS
═══════════════════════════════════════════════════════
- Verificar manualmente los logs del servidor.
- Contactar al cliente para obtener más detalles sobre el problema.
- Escalar a nivel 2 si el problema persiste.
"""

    def _update_znuny_article(self, ticket_id: int, session_id: str, 
                               subject: str, body: str, type_id: int = 10) -> bool:
        """
        Updates a Znuny ticket with a new article.
        Used by async incident processing.
        """
        url = f"{self.base_url}/Ticket/{ticket_id}"
        payload = {
            "SessionID": session_id,
            "TicketID": ticket_id,
            "Ticket": {
                "TypeID": type_id
            },
            "Article": {
                "Subject": subject,
                "Body": body,
                "ContentType": "text/plain; charset=utf8"
            }
        }
        
        try:
            r = requests.patch(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            r.raise_for_status()
            logger.info(f"✅ [Thread] Znuny ticket {ticket_id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"❌ [Thread] Failed to update Znuny ticket {ticket_id}: {e}")
            return False

    def _call_multimodal_service(self, ticket_id: int, ticket_text: str) -> Optional[Dict[str, Any]]:
        """
        Calls the multimodal-images service for visual/design ticket analysis.
        Waits for response and returns the diagnosis.
        
        Returns dict with 'type_id' and 'diagnosis' or None on failure.
        """
        multimodal_url = os.environ.get("MULTIMODAL_URL")
        if not multimodal_url:
            logger.warning("⚠️ MULTIMODAL_URL not configured - skipping visual analysis")
            return None
        endpoint = f"{multimodal_url}/diagnose"
        
        payload = {
            "ticket_id": str(ticket_id),
            "ticket_text": ticket_text,
            "use_rag": True
            # TODO: Add images support when needed
        }
        
        try:
            logger.info(f"🎨 Calling multimodal service for ticket {ticket_id}...")
            response = requests.post(
                endpoint,
                json=payload,
                timeout=120  # Visual analysis can take time
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "error":
                logger.error(f"❌ Multimodal service error: {data.get('error')}")
                return None
            
            # Handle diagnosis - can be string or array
            diagnosis = data.get("diagnosis")
            if isinstance(diagnosis, list):
                diagnosis = json.dumps(diagnosis, indent=2, ensure_ascii=False)
            
            logger.info(f"🎨 Visual diagnosis received. TypeID: {data.get('type_id')}, Time: {data.get('processing_time_ms')}ms")
            
            return {
                "type_id": data.get("type_id"),
                "diagnosis": diagnosis,
                "processing_time_ms": data.get("processing_time_ms")
            }
            
        except requests.exceptions.Timeout:
            logger.warning("⚠️ Multimodal service request timed out (120s)")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ Could not connect to multimodal service - may be down")
            return None
        except Exception as e:
            logger.warning(f"⚠️ Error calling multimodal service: {e}")
            return None

    # =========================================================================
    # MAIN ORCHESTRATOR (Follows Single Responsibility - just orchestrates)
    # =========================================================================
    
    def diagnose_and_update_ticket(self, ticket_id: int, 
                                    session_id: Optional[str] = None, 
                                    data: Optional[dict] = None) -> Dict[str, Any]:
        """
        Orchestrates the ticket diagnosis and update workflow.
        Delegates specific tasks to specialized methods.
        """
        data = data or {}
        
        # 1. Session management
        if not session_id:
            session_id = self.get_or_create_session_id()
            logger.info("SessionID obtained for operation.")

        # 2. Extract parameters
        title = data.get("titulo") or f"Ticket Update {ticket_id}"
        user = data.get("usuario") or ""
        queue_id = data.get("queue_id") or 1
        priority_id = data.get("priority_id") or 3
        state_id = data.get("state_id") or 4
        subject = data.get("subject") or "Automatic Diagnosis (AI)"

        # 3. Get ticket content
        logger.info(f"Fetching latest article for ticket {ticket_id}...")
        ticket_text = self.get_ticket_latest_article(ticket_id, session_id)
        if not ticket_text:
            raise ValueError("No ticket text found (latest article).")

        logger.info(f"📝 TEXTO DEL TICKET EXTRAÍDO:\n{ticket_text}\n" + "═"*30)

        # 4. Get RAG configuration
        tool_config = self._get_rag_tool_config()

        # 5. Generate AI diagnosis
        logger.info("Generating diagnosis from ticket...")
        diagnosis_result = self._generate_diagnosis(ticket_text, tool_config)
        
        type_id_from_ia = diagnosis_result["type_id"]
        requires_visual = diagnosis_result.get("requires_visual", False)
        diagnosis_body = diagnosis_result["diagnostico"]
        
        if not diagnosis_body or not diagnosis_body.strip():
            raise RuntimeError("AI returned empty diagnosis.")
        
        logger.info(f"Diagnosis generated. TypeID: {type_id_from_ia}, RequiresVisual: {requires_visual}")

        # 6. Route to multimodal service if visual analysis needed
        visual_result = None
        if requires_visual:
            logger.info("🎨 Ticket requires visual analysis - calling multimodal service...")
            visual_result = self._call_multimodal_service(ticket_id, ticket_text)
            
            if visual_result:
                # Use visual diagnosis instead of classic diagnosis
                diagnosis_body = visual_result["diagnosis"]
                type_id_from_ia = visual_result["type_id"] or type_id_from_ia
                logger.info(f"🎨 Using visual diagnosis. New TypeID: {type_id_from_ia}")
            else:
                logger.warning("⚠️ Visual analysis failed - using classic diagnosis as fallback")

        # 7. Process incident (conditional - only if type_id == 10)
        incident_data = self._process_incident(
            ticket_id, session_id, ticket_text, diagnosis_body, type_id_from_ia
        )

        # 8. Check if incident was delegated to background thread
        if incident_data and incident_data.get("delegated"):
            logger.info(f"🚀 Ticket {ticket_id} is INCIDENT - delegated to error_log. Skipping sync Znuny update.")
            return {
                "ok": True,
                "ticket_id": ticket_id,
                "type_id_from_ia": type_id_from_ia,
                "diagnosis_body": diagnosis_body,
                "delegated_to_error_log": True,
                "incident_data": incident_data,
                "message": "Incident delegated to error_log for async processing. Znuny will be updated by background thread."
            }

        # 9. Update Znuny ticket (only for non-incident tickets)
        logger.info(f"Sending update to ticket {ticket_id}...")
        
        # Add service identifier for traceability
        body_with_identifier = f"[Procesado por: mod_agentes]\n\n{diagnosis_body}"
        
        resp = self.update_ticket(
            ticket_id=ticket_id,
            session_id=session_id,
            title=title,
            user=user,
            queue_id=queue_id,
            priority_id=priority_id,
            state_id=state_id,
            subject=subject,
            body=body_with_identifier,
            type_id=type_id_from_ia
        )
        
        if isinstance(resp, dict) and 'error' in resp:
            raise RuntimeError(f"Failed to update Znuny: {resp['error']}")

        # 10. Build response
        result = {
            "ok": True,
            "ticket_id": ticket_id,
            "type_id_from_ia": type_id_from_ia,
            "diagnosis_body": diagnosis_body,
            "update_response": resp
        }
        
        if incident_data:
            result["incident_data"] = incident_data
            
        return result


# Singleton instance for backward compatibility if needed, 
# but generally better to instantiate where needed or use dependency injection.
# For now, we can expose a default instance to minimize breakage if other modules import it.
# However, the plan is to update the controller to use the class.