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
        if self.creds:
            self.service = build('drive', 'v3', credentials=self.creds)
            self.sheets_service = build('sheets', 'v4', credentials=self.creds)
        else:
            self.service = None
            self.sheets_service = None

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
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Es un Google Sheet, leer la primera hoja por defecto
                print("📊 Detectado Google Sheet. Intentando leer hoja completa...")
                return self.get_sheet_values(file_id)
            else:
                # Para otros archivos, intentar descarga directa (si fuera necesario en el futuro)
                # Por ahora solo soportamos Google Docs para este caso de uso
                print(f"⚠️ Tipo de archivo no soportado para lectura directa de texto: {mime_type}")
                return ""

        except Exception as e:
            print(f"❌ Error leyendo archivo de Drive {file_id}: {e}")
            return ""

    def get_sheet_values(self, spreadsheet_id, range_name="A:Z"):
        """
        Lee valores de un Google Sheet.
        Por defecto lee todas las columnas de la primera hoja (A:Z).
        """
        if not self.sheets_service:
            print("⚠️ Servicio de Sheets no inicializado.")
            return ""
            
        try:
            sheet = self.sheets_service.spreadsheets()
            result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                        range=range_name).execute()
            values = result.get('values', [])

            if not values:
                return "No data found."
            
            return "\n".join([", ".join(row) for row in values])

        except Exception as e:
            print(f"❌ Error leyendo Google Sheet {spreadsheet_id}: {e}")
            return ""

    def filter_and_format_incidents(self, spreadsheet_id, sheet_name="2. Consolidado Incidentes"):
        """
        Filtra y formatea incidentes desde columnas L1 y AC1.
        Solo incluye filas donde ambos campos estén completos.
        
        Args:
            spreadsheet_id: ID del Google Sheet
            sheet_name: Nombre de la hoja (default: "2. Consolidado Incidentes")
            
        Returns:
            list: Lista de documentos formateados, uno por incidente válido
        """
        if not self.sheets_service:
            print("⚠️ Servicio de Sheets no inicializado.")
            return []
        
        try:
            print(f"📊 Leyendo incidentes desde '{sheet_name}' (L:AC)...")
            
            sheet = self.sheets_service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!L:AC"
            ).execute()
            
            values = result.get('values', [])
            incidents = []
            
            # Iterar desde fila 1 (saltar header)
            for i, row in enumerate(values[1:], start=1):
                # Columna L es índice 0, AC es índice 17 (L=12, AC=29)
                l1_cell = row[0] if len(row) > 0 else ""
                ac1_cell = row[17] if len(row) > 17 else ""
                
                if l1_cell.strip() and ac1_cell.strip():
                    incidents.append(f"=== INCIDENTE #{i} ===\nL1: {l1_cell.strip()}\nAC1: {ac1_cell.strip()}\n---\n")
            
            print(f"✅ Procesados {len(incidents)} incidentes. Omitidos {len(values[1:]) - len(incidents)}")
            return incidents
            
        except Exception as e:
            print(f"❌ Error filtrando incidentes: {e}")
            return []

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
        temp_filename = f"temp_drive_{file_id}.txt"
        try:
            print(f"🔄 Sincronizando Drive {file_id} -> KB {store_name}...")
            
            content = self.get_file_content(file_id)
            if not content:
                return False
                
            with open(temp_filename, "w") as f:
                f.write(content)
                
            return kb_service.upload_and_index_file(store_name, temp_filename)
                
        except Exception as e:
            print(f"❌ Error en sincronización: {e}")
            return False
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
