import os
import json
import time
import logging
import requests
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
            
        # Logic: Take the second to last article if available (assuming last is notification), else last.
        if len(sorted_articles) >= 2:
            last_relevant = sorted_articles[-2] 
        else:
            last_relevant = sorted_articles[-1]
        
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
        Returns dict with 'type_id' and 'diagnostico'.
        """
        response_data = self.agent_service.diagnose_ticket(ticket_text, tool_config)
        
        if isinstance(response_data, str):
            return {"type_id": None, "diagnostico": response_data}
        
        return {
            "type_id": response_data.get("type_id"),
            "diagnostico": response_data.get("diagnostico")
        }

    def _build_incident_data(self, ticket_id: int, metadata: dict, 
                              diagnosis_body: str, type_id: int, 
                              client_info: dict) -> dict:
        """Builds the incident data structure."""
        import datetime
        return {
            "ticket_id": ticket_id,
            "ticket_number": metadata.get("ticket_number"),
            "title": metadata.get("title"),
            "type_id": type_id,
            "type_name": "Incidente",
            "diagnostico": diagnosis_body,
            "cliente_znuny": {
                "customer_id": metadata.get("customer_id"),
                "customer_user": metadata.get("customer_user")
            },
            "cliente_real": client_info,
            "queue": metadata.get("queue"),
            "state": metadata.get("state"),
            "priority": metadata.get("priority"),
            "created": metadata.get("created"),
            "processed_at": datetime.datetime.utcnow().isoformat() + "Z"
        }

    def _save_incident_to_file(self, ticket_id: int, incident_data: dict) -> str:
        """Saves incident data to JSON file. Returns the file path."""
        incidents_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "incidents")
        os.makedirs(incidents_dir, exist_ok=True)
        
        json_path = os.path.join(incidents_dir, f"ticket_{ticket_id}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(incident_data, f, ensure_ascii=False, indent=2)
        
        return json_path

    def _process_incident(self, ticket_id: int, session_id: str, 
                          ticket_text: str, diagnosis_body: str, 
                          type_id: int) -> Optional[dict]:
        """
        Processes incident tickets (type_id=10).
        Extracts client info and saves to JSON.
        Returns incident_data or None.
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
            
            # Build and save incident data
            incident_data = self._build_incident_data(
                ticket_id, metadata, diagnosis_body, type_id, client_info
            )
            
            json_path = self._save_incident_to_file(ticket_id, incident_data)
            
            logger.info(f"✅ Incident data saved to: {json_path}")
            logger.info(f"📍 Cliente real detectado: {client_info.get('entidad', 'No identificado')}")
            
            # Notify external log monitor service
            self._notify_log_monitor(incident_data)
            
            return incident_data
            
        except Exception as e:
            logger.error(f"❌ Error processing incident data: {e}")
            return None

    def _notify_log_monitor(self, incident_data: dict) -> bool:
        """
        Notifies the external log monitor service about the incident.
        Fire-and-forget pattern - does not block on failure.
        """
        log_monitor_url = os.environ.get("LOG_MONITOR_URL", "http://localhost:8000")
        endpoint = f"{log_monitor_url}/analyze-incident"
        
        try:
            response = requests.post(
                endpoint,
                json=incident_data,
                timeout=10
            )
            logger.info(f"📤 Incident sent to log monitor: {response.status_code}")
            return True
        except requests.exceptions.Timeout:
            logger.warning("⚠️ Log monitor request timed out - continuing without logs")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("⚠️ Could not connect to log monitor - service may be down")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Error notifying log monitor: {e}")
            return False

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

        # 4. Get RAG configuration
        tool_config = self._get_rag_tool_config()

        # 5. Generate AI diagnosis
        logger.info("Generating diagnosis from ticket...")
        diagnosis_result = self._generate_diagnosis(ticket_text, tool_config)
        
        type_id_from_ia = diagnosis_result["type_id"]
        diagnosis_body = diagnosis_result["diagnostico"]
        
        if not diagnosis_body or not diagnosis_body.strip():
            raise RuntimeError("AI returned empty diagnosis.")
        
        logger.info(f"Diagnosis generated. TypeID: {type_id_from_ia}")

        # 6. Process incident (conditional)
        incident_data = self._process_incident(
            ticket_id, session_id, ticket_text, diagnosis_body, type_id_from_ia
        )

        # 7. Update Znuny ticket
        logger.info(f"Sending update to ticket {ticket_id}...")
        resp = self.update_ticket(
            ticket_id=ticket_id,
            session_id=session_id,
            title=title,
            user=user,
            queue_id=queue_id,
            priority_id=priority_id,
            state_id=state_id,
            subject=subject,
            body=diagnosis_body,
            type_id=type_id_from_ia
        )
        
        if isinstance(resp, dict) and 'error' in resp:
            raise RuntimeError(f"Failed to update Znuny: {resp['error']}")

        # 8. Build response
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