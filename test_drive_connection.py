import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Alcances (Scopes) para Drive y Sheets
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]

# Ruta correcta al archivo de permisos/credenciales
ARCHIVO_CREDENCIALES = os.path.join(os.path.dirname(__file__), 'env_vars', 'permisos.json')

def probar_conexion_drive():
    """
    Prueba la conexión a Google Drive y lista archivos.
    """
    print(f"Usando archivo de credenciales: {ARCHIVO_CREDENCIALES}")
    
    if not os.path.exists(ARCHIVO_CREDENCIALES):
        print(f"ERROR: No se encontró el archivo de credenciales en {ARCHIVO_CREDENCIALES}")
        return False

    try:
        credenciales = service_account.Credentials.from_service_account_file(
            ARCHIVO_CREDENCIALES, scopes=SCOPES)

        servicio_drive = build('drive', 'v3', credentials=credenciales)
        
        print("✅ Autenticación exitosa con Google.")
        print("Listando archivos de Drive...")
        
        resultados = servicio_drive.files().list(
            pageSize=10, fields="nextPageToken, files(id, name, mimeType)").execute()
        items = resultados.get('files', [])

        if not items:
            print("No se encontraron archivos en Drive.")
        else:
            print("Archivos encontrados:")
            for item in items:
                print(f"  - {item['name']} (ID: {item['id']}, Tipo: {item['mimeType']})")
                
        return credenciales
    except Exception as e:
        print(f"❌ Error conectando a Drive: {e}")
        return None

def leer_google_doc(credenciales, file_id):
    """
    Lee el contenido de un Google Doc exportándolo a texto plano usando la API de Drive.
    No requiere la API de Docs, solo la de Drive.
    """
    try:
        service = build('drive', 'v3', credentials=credenciales)
        
        print(f"\n--- Leyendo Documento: {file_id} ---")
        
        # Exportar a texto plano
        # Nota: export_media descarga el contenido convertido
        request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        response = request.execute()
        
        # response es bytes, decodificar
        contenido = response.decode('utf-8')
        
        print("✅ Contenido del documento:")
        print("-" * 40)
        print(contenido)
        print("-" * 40)
                
        return True

    except Exception as e:
        print(f"❌ Error leyendo el documento: {e}")
        return False

if __name__ == '__main__':
    print("Intentando conectar a Google Drive...")
    
    creds = probar_conexion_drive()
    
    if creds:
        # ID del documento "tickets" encontrado
        DOC_ID = "13dEi_PJb68T7NEJ2XcHdYhdsbs-iZPbuaVjb-GR_o6k"
        leer_google_doc(creds, DOC_ID)

