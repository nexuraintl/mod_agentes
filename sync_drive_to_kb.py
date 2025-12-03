import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.google_drive_service import GoogleDriveService
from services.knowledge_base_service import KnowledgeBaseService

def sync_production_data():
    print("🚀 Iniciando sincronización de Producción (Drive -> Gemini KB)...")
    
    drive_service = GoogleDriveService()
    kb_service = KnowledgeBaseService()
    
    # ID del documento "tickets" (Producción)
    DOC_ID = "13dEi_PJb68T7NEJ2XcHdYhdsbs-iZPbuaVjb-GR_o6k"
    
    # Nombre del Store
    STORE_NAME = "Znuny_Tickets_KB"
    
    # Asegurar que el store exista
    store_id = kb_service.get_or_create_store(display_name=STORE_NAME)
    if not store_id:
        print("❌ No se pudo obtener el Store ID.")
        return

    # Ejecutar sincronización usando el nuevo método integrado
    success = drive_service.sync_file_to_knowledge_base(DOC_ID, kb_service, store_id)
    
    if success:
        print("\n✅ ¡Sincronización Exitosa! La base de conocimiento está actualizada.")
    else:
        print("\n❌ La sincronización falló.")

if __name__ == "__main__":
    sync_production_data()
