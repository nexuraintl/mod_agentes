import os
import sys

# Agregar el directorio raíz al path para importar los servicios
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.google_drive_service import GoogleDriveService

def test_sheets_connection():
    print("🚀 Iniciando prueba de conexión a Google Sheets...")
    
    # 1. Inicializar servicio
    drive_service = GoogleDriveService()
    
    if not drive_service.sheets_service:
        print("❌ Falló la inicialización del servicio de Sheets.")
        return

    print("✅ Servicio de Sheets inicializado correctamente.")
    
    # 2. Solicitar ID de la hoja al usuario (o usar uno hardcodeado si se prefiere para pruebas rápidas)
    spreadsheet_id = input("\n👉 Por favor, introduce el ID del Google Sheet para probar: ").strip()
    
    if not spreadsheet_id:
        print("⚠️ No se proporcionó ID. Abortando prueba de lectura.")
        return

    # 3. Intentar leer
    print(f"\n📊 Intentando leer el Sheet: {spreadsheet_id}")
    content = drive_service.get_sheet_values(spreadsheet_id)
    
    if content:
        print("\n✅ Lectura exitosa! Primeras 500 caracteres del contenido:")
        print("-" * 50)
        print(content[:500] + "..." if len(content) > 500 else content)
        print("-" * 50)
    else:
        print("\n❌ No se pudo leer contenido o la hoja está vacía.")

if __name__ == "__main__":
    test_sheets_connection()
