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
            
            # Convertir lista de listas a string para el KB
            text_content = []
            for row in values:
                text_content.append(", ".join(row))
            
            return "\n".join(text_content)

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
            print(f"📊 Leyendo incidentes desde '{sheet_name}'...")
            
            # Leer columnas L1 (L) y AC1 (AC) completas
            sheet = self.sheets_service.spreadsheets()
            
            # Leer L1 (columna L, índice 11)
            l1_result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!L:L"
            ).execute()
            l1_values = l1_result.get('values', [])
            
            # Leer AC1 (columna AC, índice 28)
            ac1_result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!AC:AC"
            ).execute()
            ac1_values = ac1_result.get('values', [])
            
            # Normalizar longitudes (AC1 puede ser más corta)
            max_rows = max(len(l1_values), len(ac1_values))
            
            incidents = []
            skipped_count = 0
            
            # Iterar desde fila 1 (saltar header en fila 0)
            for i in range(1, max_rows):
                # Obtener valores, manejar filas faltantes
                l1_cell = l1_values[i][0] if i < len(l1_values) and len(l1_values[i]) > 0 else ""
                ac1_cell = ac1_values[i][0] if i < len(ac1_values) and len(ac1_values[i]) > 0 else ""
                
                # Filtrar: ambos campos deben estar completos
                if not l1_cell.strip() or not ac1_cell.strip():
                    skipped_count += 1
                    continue
                
                # Formatear como documento estructurado
                incident_doc = f"""=== INCIDENTE #{i} ===
L1: {l1_cell.strip()}
AC1: {ac1_cell.strip()}
---
"""
                incidents.append(incident_doc)
            
            print(f"✅ Procesados {len(incidents)} incidentes válidos")
            print(f"⚠️ Omitidas {skipped_count} filas con campos vacíos")
            
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
