#!/usr/bin/env python3
"""
Script para probar la obtención de metadata de un ticket y guardarla en JSON.
Uso: python tests/test_ticket_metadata.py <ticket_id>
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
from dotenv import load_dotenv
import json

load_dotenv("env_vars/.env")

from services.update_service import ZnunyService

def test_get_metadata(ticket_id: int):
    """Obtiene la metadata de un ticket y la guarda en JSON."""
    
    service = ZnunyService()
    
    print(f"🔐 Obteniendo SessionID...")
    session_id = service.get_or_create_session_id()
    print(f"✅ SessionID: {session_id[:20]}...")
    
    print(f"📋 Obteniendo metadata del ticket {ticket_id}...")
    metadata = service.get_ticket_metadata(ticket_id, session_id)
    
    if not metadata:
        print("❌ No se pudo obtener la metadata del ticket")
        return
    
    # Crear directorio logs si no existe
    os.makedirs("logs", exist_ok=True)
    
    # Guardar en JSON
    output_file = f"logs/ticket_{ticket_id}_metadata.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Metadata guardada en: {output_file}")
    print("\n📄 Contenido:")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tests/test_ticket_metadata.py <ticket_id>")
        print("Ejemplo: python tests/test_ticket_metadata.py 268")
        sys.exit(1)
    
    ticket_id = int(sys.argv[1])
    test_get_metadata(ticket_id)
