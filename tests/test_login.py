import json
import pytest
from services.update_service import ZnunyService
import requests

class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"SessionID": "fake-session-123"}
        self.text = json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")

    def json(self):
        return self._payload


def fake_patch(url, data=None, headers=None, timeout=None):
    # Devuelve una respuesta simulada con SessionID
    return FakeResponse(status_code=200, payload={"SessionID": "fake-session-123"})


def test_login_create_session_monkeypatch(monkeypatch):
    """Parchea requests.patch para simular login y comprobar el SessionID usando ZnunyService."""
    # Asegurarse de que las variables de entorno necesarias existan
    import os
    os.environ.setdefault("ZNUNY_BASE_API", "http://localhost/otrs")
    os.environ.setdefault("ZNUNY_USERNAME", "rvargas")
    os.environ.setdefault("ZNUNY_PASSWORD", "nexura2025")

    # Parchear requests.patch
    monkeypatch.setattr(requests, "patch", fake_patch)

    # Instanciar el servicio
    service = ZnunyService()
    
    # Llamar al método privado (o público si se prefiere probar get_or_create_session_id)
    # Probamos _login_create_session directamente para verificar la lógica de autenticación
    session_id = service._login_create_session()

    assert session_id == "fake-session-123"

def test_get_or_create_session_caching(monkeypatch):
    """Verifica que get_or_create_session_id use la caché."""
    monkeypatch.setattr(requests, "patch", fake_patch)
    
    service = ZnunyService()
    
    # Primera llamada: crea sesión
    sid1 = service.get_or_create_session_id()
    assert sid1 == "fake-session-123"
    
    # Forzamos un cambio en la variable privada para verificar que NO se llama de nuevo a login
    # (Si se llamara a login, devolvería "fake-session-123" de nuevo, así que cambiamos el valor en cache)
    service._cached_session_id = "cached-session-999"
    
    # Segunda llamada: debe devolver el valor cacheado
    sid2 = service.get_or_create_session_id()
    assert sid2 == "cached-session-999"

