import pytest
from unittest.mock import MagicMock
from services.agent_service import AgentService

def test_diagnose_ticket_valid_json():
    """Test that diagnose_ticket correctly parses valid JSON from AI."""
    service = AgentService()
    
    # Mock ADKClient
    service.adk_client = MagicMock()
    service.adk_client.diagnose_ticket.return_value = '{"type_id": 14, "diagnostico": "Valid diagnosis"}'
    
    result = service.diagnose_ticket("some ticket text")
    
    assert isinstance(result, dict)
    assert result["type_id"] == 14
    assert result["diagnostico"] == "Valid diagnosis"

def test_diagnose_ticket_json_in_markdown():
    """Test that diagnose_ticket handles JSON wrapped in markdown code blocks."""
    service = AgentService()
    service.adk_client = MagicMock()
    service.adk_client.diagnose_ticket.return_value = '```json\n{"type_id": 15, "diagnostico": "Markdown diagnosis"}\n```'
    
    result = service.diagnose_ticket("some ticket text")
    
    assert result["type_id"] == 15
    assert result["diagnostico"] == "Markdown diagnosis"

def test_diagnose_ticket_invalid_json():
    """Test that diagnose_ticket returns raw text if JSON parsing fails."""
    service = AgentService()
    service.adk_client = MagicMock()
    service.adk_client.diagnose_ticket.return_value = "Just plain text diagnosis"
    
    result = service.diagnose_ticket("some ticket text")
    
    assert result["type_id"] is None
    assert result["diagnostico"] == "Just plain text diagnosis"

def test_diagnose_ticket_empty_response():
    """Test handling of empty response from AI."""
    service = AgentService()
    service.adk_client = MagicMock()
    service.adk_client.diagnose_ticket.return_value = None
    
    result = service.diagnose_ticket("some ticket text")
    
    assert "Diagnóstico automático no disponible" in result
