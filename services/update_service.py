import os
import json
import time
import logging
import requests
from typing import Optional, Dict, Any, Union

from .agent_service import AgentService
from .google_drive_service import GoogleDriveService

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
        self._drive_service: Optional[GoogleDriveService] = None

    @property
    def drive_service(self) -> GoogleDriveService:
        if self._drive_service is None:
            self._drive_service = GoogleDriveService()
        return self._drive_service

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

    def diagnose_and_update_ticket(self, ticket_id: int, session_id: Optional[str] = None, data: Optional[dict] = None) -> Dict[str, Any]:
        """
        Generates an AI diagnosis and updates the ticket in Znuny.
        """
        data = data or {}
        
        if not session_id:
            session_id = self.get_or_create_session_id()
            logger.info("SessionID obtained for operation.")

        # Default values
        title = data.get("titulo") or f"Ticket Update {ticket_id}"
        user = data.get("usuario") or ""
        queue_id = data.get("queue_id") or 1
        priority_id = data.get("priority_id") or 3
        state_id = data.get("state_id") or 4
        subject = data.get("subject") or "Automatic Diagnosis (AI)"

        logger.info(f"Fetching latest article for ticket {ticket_id}...")
        ticket_text = self.get_ticket_latest_article(ticket_id, session_id)

        if not ticket_text:
            raise ValueError("No ticket text found (latest article).")

        logger.info("Generating diagnosis from ticket...")
        
        # Fetch examples from Drive
        examples_context = ""
        try:
            # ID del documento "tickets"
            DOC_ID = "13dEi_PJb68T7NEJ2XcHdYhdsbs-iZPbuaVjb-GR_o6k"
            examples_context = self.drive_service.get_file_content(DOC_ID)
            if examples_context:
                logger.info("✅ Examples fetched from Drive successfully.")
            else:
                logger.warning("⚠️ Failed to fetch examples from Drive (empty content).")
        except Exception as e:
            logger.error(f"❌ Error fetching examples from Drive: {e}")

        response_data = self.agent_service.diagnose_ticket(ticket_text, examples_context) 
        
        # Handle response from AgentService (which might be a string or dict depending on implementation)
        # Assuming AgentService returns a dict as per previous code
        if isinstance(response_data, str):
             # Fallback if it returns string
             type_id_from_ia = None
             diagnosis_body = response_data
        else:
            type_id_from_ia = response_data.get("type_id")
            diagnosis_body = response_data.get("diagnostico")

        if not diagnosis_body or not diagnosis_body.strip():
            raise RuntimeError("AI returned empty diagnosis.")

        logger.info(f"Diagnosis generated. TypeID: {type_id_from_ia}")

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

        return {
            "ok": True,
            "ticket_id": ticket_id,
            "type_id_from_ia": type_id_from_ia,
            "diagnosis_body": diagnosis_body,
            "update_response": resp
        }

# Singleton instance for backward compatibility if needed, 
# but generally better to instantiate where needed or use dependency injection.
# For now, we can expose a default instance to minimize breakage if other modules import it.
# However, the plan is to update the controller to use the class.