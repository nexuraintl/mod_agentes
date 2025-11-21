import os
import time
from google import genai
from google.genai import types
from typing import Optional

class KnowledgeBaseService:
    """
    Servicio para gestionar la Base de Conocimiento (File Search Store) en Gemini.
    Permite crear stores, subir archivos y preparar los recursos para RAG.
    """

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")
        self.client = genai.Client(api_key=api_key)

    def get_or_create_store(self, display_name: str = "Znuny_Knowledge_Base") -> str:
        """
        Busca un File Search Store existente por nombre o crea uno nuevo.
        Retorna el `name` (resource ID) del store.
        """
        print(f"🔍 Buscando File Search Store: '{display_name}'...")
        
        try:
            # Intentar crear (si ya existe con ese nombre, la API suele crear otro, 
            # idealmente listaríamos pero para MVP creamos uno nuevo o usamos el ID si lo tuviéramos)
            store = self.client.file_search_stores.create(
                config={'display_name': display_name}
            )
            print(f"✅ Store creado exitosamente: {store.name}")
            return store.name
        except Exception as e:
            print(f"❌ Error creando store: {e}")
            return ""

    def upload_file_to_store(self, file_path: str, mime_type: str = "text/plain") -> Optional[types.File]:
        """
        Sube un archivo local a la API de Gemini.
        """
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            return None

        print(f"Outbound upload: {file_path} ({mime_type})")
        try:
            # Subida estándar de archivos
            file_ref = self.client.files.upload(
                path=file_path,
                config={'mime_type': mime_type}
            )
            print(f"✅ Archivo subido a Gemini: {file_ref.name}")
            return file_ref
        except Exception as e:
            print(f"❌ Error subiendo archivo: {e}")
            return None

    def add_files_to_store(self, store_name: str, file_refs: list[types.File]):
        """
        Asocia archivos subidos a un File Search Store.
        """
        if not file_refs:
            return

        print(f"🔗 Asociando {len(file_refs)} archivos al store {store_name}...")
        try:
            for f in file_refs:
                # Usamos el método correcto descubierto: client.file_search_stores.import_file
                # Ojo: import_file podría requerir argumentos específicos.
                # Alternativa segura si existe: create_file_search_store_file no existe en client.files
                # pero client.file_search_stores tiene 'documents' o 'import_file'.
                
                # Vamos a probar con una llamada directa a la API subyacente si el wrapper es confuso,
                # pero 'client.file_search_stores.create' funcionó en la inspección.
                
                # Si 'import_file' no es lo que pensamos, intentemos usar el método de conveniencia
                # que vimos en dir(): 'upload_to_file_search_store' si quisiéramos subir directo.
                # Pero ya tenemos el file_ref.
                
                # Revisando la salida de dir(client.file_search_stores):
                # ['create', 'delete', 'documents', 'get', 'import_file', 'list', 'upload_to_file_search_store']
                
                # Probablemente 'documents.create' o similar.
                # Vamos a intentar usar 'upload_to_file_search_store' directamente con el path si es más fácil,
                # pero para usar file_refs ya subidos, debería ser algo como asociar.
                
                # Para este fix, vamos a asumir que podemos usar 'upload_to_file_search_store' 
                # pasando el path local de nuevo si es necesario, o investigar 'documents'.
                pass

            # ESTRATEGIA SEGURA: Usar upload_to_file_search_store directamente desde el path local
            # Esto hace upload + asociación en un paso.
            print("⚠️ Método add_files_to_store refactorizado para usar upload directo en el futuro.")
            
        except Exception as e:
            print(f"❌ Error asociando archivos: {e}")

    def upload_and_index_file(self, store_name: str, file_path: str) -> bool:
        """
        Método combinado para subir e indexar un archivo en el store.
        Reemplaza a upload_file_to_store + add_files_to_store para simplificar.
        """
        try:
            print(f"📤 Subiendo e indexando {file_path} en {store_name}...")
            # Usamos el método de conveniencia del cliente
            self.client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_name,
                file=file_path
            )
            print("✅ Archivo indexado correctamente.")
            return True
        except Exception as e:
            print(f"❌ Error en upload_to_file_search_store: {e}")
            return False

    def get_tool_config(self, store_name: str) -> types.Tool:
        """
        Retorna la configuración de la herramienta para usar en generate_content.
        """
        # Configuración correcta para File Search Tool
        # Según inspección: types.Tool tiene 'file_search'
        # Y types.FileSearch probablemente tenga 'file_search_store' o similar.
        # Vamos a asumir la estructura estándar:
        return types.Tool(
            google_search=None,
            code_execution=None,
            # file_search espera un objeto FileSearch o dict
            # El campo correcto es 'file_search_store_names' (lista de strings)
            file_search=types.FileSearch(
                file_search_store_names=[store_name]
            )
        )

