import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.knowledge_base_service import KnowledgeBaseService
from utils.adk_client import ADKClient

def verify_rag():
    print("🚀 Iniciando verificación de RAG con Gemini File Search Store...")
    
    kb_service = KnowledgeBaseService()
    
    # 1. Crear un archivo de prueba local
    test_file_path = "test_rag_doc.txt"
    with open(test_file_path, "w") as f:
        f.write("""
        ERROR CONOCIDO: Error 999 en Módulo de Ventas
        Causa: El servidor de base de datos 'DB-SALES-01' tiene un bloqueo en la tabla 'invoices'.
        Solución: Ejecutar el script 'unlock_sales.sh' en el servidor y reiniciar el servicio 'sales-api'.
        Tipo: Incidente (10).
        """)
    print(f"📄 Archivo de prueba creado: {test_file_path}")

    try:
        # 2. Crear/Obtener Store
        store_name = kb_service.get_or_create_store(display_name="Test_RAG_Store")
        if not store_name:
            print("❌ Falló la creación del Store.")
            return

        # 3. Subir e indexar archivo
        success = kb_service.upload_and_index_file(store_name, test_file_path)
        if not success:
            print("❌ Falló la subida e indexación del archivo.")
            return

        # 5. Probar ADKClient con la herramienta
        print("\n🤖 Probando ADKClient con RAG...")
        client = ADKClient()
        
        # Ticket que requiere la info del archivo
        ticket_text = "Ayuda, me sale el Error 999 cuando intento facturar en Ventas. No sé qué hacer."
        
        tool_config = kb_service.get_tool_config(store_name)
        
        # Llamada real a Gemini
        response = client.diagnose_ticket(ticket_text, tool_config=tool_config)
        
        print("\n📝 Respuesta de Gemini:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        
        if "unlock_sales.sh" in str(response):
            print("✅ ÉXITO: El modelo recuperó la información del archivo (mencionó 'unlock_sales.sh').")
        else:
            print("⚠️ ADVERTENCIA: El modelo no pareció usar la información específica del archivo.")

    except Exception as e:
        print(f"❌ Error durante la verificación: {e}")
    finally:
        # Limpieza (opcional)
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

if __name__ == "__main__":
    verify_rag()
