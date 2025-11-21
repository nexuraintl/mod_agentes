import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

class GoogleDriveService:
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets.readonly'
    ]
    
    def __init__(self):
        self.creds = self._authenticate()
        self.service = build('drive', 'v3', credentials=self.creds) if self.creds else None

    def _authenticate(self):
        """Autentica usando el archivo de credenciales."""
        creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'env_vars', 'permisos.json')
        
        if not os.path.exists(creds_path):
            print(f"ERROR: No se encontró el archivo de credenciales en {creds_path}")
            return None
            
        try:
            return service_account.Credentials.from_service_account_file(
                creds_path, scopes=self.SCOPES)
        except Exception as e:
            print(f"❌ Error de autenticación con Google: {e}")
            return None

    def get_file_content(self, file_id):
        """
        Obtiene el contenido de un archivo de Drive.
        Si es un Google Doc, lo exporta a texto plano.
        """
        if not self.service:
            print("⚠️ Servicio de Drive no inicializado.")
            return ""

        try:
            # Primero obtenemos metadatos para saber el tipo MIME
            file_metadata = self.service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType')
            
            print(f"📄 Leyendo archivo: {file_metadata.get('name')} ({mime_type})")

            if mime_type == 'application/vnd.google-apps.document':
                # Es un Google Doc, exportar a texto
                request = self.service.files().export_media(fileId=file_id, mimeType='text/plain')
                response = request.execute()
                return response.decode('utf-8')
            else:
                # Para otros archivos, intentar descarga directa (si fuera necesario en el futuro)
                # Por ahora solo soportamos Google Docs para este caso de uso
                print(f"⚠️ Tipo de archivo no soportado para lectura directa de texto: {mime_type}")
                return ""

        except Exception as e:
            print(f"❌ Error leyendo archivo de Drive {file_id}: {e}")
            return ""

    def sync_file_to_knowledge_base(self, file_id: str, kb_service, store_name: str) -> bool:
        """
        Descarga el contenido de un archivo de Drive y lo sube al Knowledge Base Store.
        
        Args:
            file_id: ID del archivo en Google Drive.
            kb_service: Instancia de KnowledgeBaseService.
            store_name: Nombre del store en Gemini.
            
        Returns:
            bool: True si la sincronización fue exitosa.
        """
        try:
            print(f"🔄 Sincronizando archivo Drive {file_id} a KB {store_name}...")
            
            # 1. Obtener contenido
            content = self.get_file_content(file_id)
            if not content:
                print("❌ No se pudo obtener contenido de Drive.")
                return False
                
            # 2. Guardar en archivo temporal
            temp_filename = f"temp_drive_{file_id}.txt"
            with open(temp_filename, "w") as f:
                f.write(content)
                
            # 3. Subir a Knowledge Base
            success = kb_service.upload_and_index_file(store_name, temp_filename)
            
            # 4. Limpieza
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            if success:
                print("✅ Sincronización completada.")
                return True
            else:
                print("❌ Falló la subida a Knowledge Base.")
                return False
                
        except Exception as e:
            print(f"❌ Error en sincronización: {e}")
            # Asegurar limpieza en caso de error
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                os.remove(temp_filename)
            return False
