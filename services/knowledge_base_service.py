import os
from google import genai
from google.genai import types

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
            # 1. Listar stores existentes para evitar duplicados
            for store in self.client.file_search_stores.list():
                if store.display_name == display_name:
                    print(f"✅ Store encontrado: {store.name}")
                    return store.name
            
            # 2. Si no existe, crear
            print(f"⚠️ No encontrado. Creando nuevo store '{display_name}'...")
            store = self.client.file_search_stores.create(
                config={'display_name': display_name}
            )
            print(f"✅ Store creado exitosamente: {store.name}")
            return store.name
        except Exception as e:
            print(f"❌ Error gestionando store: {e}")
            return ""


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

