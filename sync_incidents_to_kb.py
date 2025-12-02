#!/usr/bin/env python3
"""
Script para sincronizar incidentes desde Google Sheets al Knowledge Base.
Filtra y formatea datos de las columnas L1 y AC1.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.google_drive_service import GoogleDriveService
from services.knowledge_base_service import KnowledgeBaseService


def sync_incidents_to_kb():
    """Sincroniza incidentes filtrados al Knowledge Base"""
    
    # Configuración
    SPREADSHEET_ID = "1YNl-KmBHEMI8QRyoHdSKTl9B1Auu6nwQkzTWEcymAQ4"
    SHEET_NAME = "2. Consolidado Incidentes"
    KB_STORE_NAME = "nexura_incidents_kb"
    
    print("🚀 Iniciando sincronización de incidentes...")
    
    # 1. Inicializar servicios
    drive_service = GoogleDriveService()
    kb_service = KnowledgeBaseService()
    
    if not drive_service.sheets_service:
        print("❌ No se pudo inicializar el servicio de Sheets.")
        return False
    
    # 2. Filtrar y formatear incidentes
    print(f"\n📊 Extrayendo incidentes desde '{SHEET_NAME}'...")
    incidents = drive_service.filter_and_format_incidents(
        SPREADSHEET_ID,
        SHEET_NAME
    )
    
    if not incidents:
        print("⚠️ No se encontraron incidentes válidos para indexar.")
        return False
    
    print(f"\n✅ {len(incidents)} incidentes listos para indexar")
    
    # 3. Crear/verificar Knowledge Base Store
    print(f"\n🗄️ Preparando Knowledge Base '{KB_STORE_NAME}'...")
    kb_service.create_store(KB_STORE_NAME)
    
    # 4. Indexar cada incidente
    print("\n📤 Subiendo incidentes al Knowledge Base...")
    success_count = 0
    
    for idx, incident_doc in enumerate(incidents, 1):
        # Guardar temporalmente
        temp_filename = f"temp_incident_{idx}.txt"
        
        try:
            with open(temp_filename, "w", encoding="utf-8") as f:
                f.write(incident_doc)
            
            # Subir al KB
            if kb_service.upload_and_index_file(KB_STORE_NAME, temp_filename):
                success_count += 1
                if idx % 50 == 0:  # Progress cada 50 incidentes
                    print(f"  ✓ Procesados {idx}/{len(incidents)} incidentes...")
            
        except Exception as e:
            print(f"  ⚠️ Error en incidente #{idx}: {e}")
        
        finally:
            # Limpiar archivo temporal
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
    
    # 5. Resumen
    print(f"\n{'='*50}")
    print(f"✅ Sincronización completada")
    print(f"📊 Total incidentes: {len(incidents)}")
    print(f"✓ Indexados exitosamente: {success_count}")
    print(f"✗ Fallidos: {len(incidents) - success_count}")
    print(f"{'='*50}\n")
    
    return success_count > 0


if __name__ == "__main__":
    success = sync_incidents_to_kb()
    sys.exit(0 if success else 1)
