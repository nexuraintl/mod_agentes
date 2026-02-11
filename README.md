# Nexura IA: Microservicio mod_agentes

Este microservicio es el núcleo de procesamiento de tickets para la plataforma de soporte de Nexura. Utiliza IA avanzada (Gemini 2.5) para diagnosticar, clasificar y delegar tickets provenientes de Znuny (OTRS) de manera automática y eficiente.

## 🚀 Funcionalidades Principales

### 1. Diagnóstico Automático con RAG
El sistema analiza el contenido de los tickets y consulta una **Base de Conocimiento (RAG)** para proporcionar respuestas basadas en experiencias previas y documentación técnica subida a Google Drive.

### 2. Delegación Asíncrona de Incidentes
Cuando un ticket se clasifica como un **Incidente (TypeID: 10)**:
- El microservicio extrae la entidad afectada (el cliente real).
- Delega el análisis profundo a un servicio externo de monitoreo de logs (`error_log`) mediante hilos secundarios (`ThreadPoolExecutor`).
- Permite que Znuny reciba una respuesta inmediata mientras el análisis exhaustivo ocurre en segundo plano.

### 3. Modo de Emergencia y Prioridad Crítica
Implementado recientemente para manejar crisis de seguridad:
- **Detección de Criticidad**: Escala de 1 a 10 para cada ticket.
- **Alertas de Seguridad**: Identificación de ransomware, robo de datos o hackeos.
- **Protocolo Inmediato**: Si la criticidad es >= 9, el sistema inserta un encabezado de **Protocolo de Emergencia** con pasos obligatorios para el técnico de guardia.
- **Asuntos Dinámicos**: Modificación del asunto del ticket para incluir advertencias visuales (`!!! ALERTA CRÍTICA SEGURIDAD !!!`).

## 🛠️ Arquitectura de Código

- `controllers/agent_controller.py`: Maneja los webhooks de entrada y la orquestación inicial.
- `services/update_service.py`: Contiene la lógica de actualización en Znuny, la gestión de hilos y el **Modo Emergencia**.
- `services/agent_service.py`: Interfaz con el cliente de IA para diagnóstico y extracción de entidades.
- `utils/adk_client.py`: Cliente de bajo nivel para Gemini que gestiona los prompts, el RAG y el análisis de criticidad.
- `env_vars/.env`: Configuración de claves de API y endpoints (No se versiona).

## 🔧 Configuración y Ejecución

### Requisitos
- Python 3.12+
- Entorno virtual (ej: `env_new`)
- Clave de API de Google Gemini

### Instalación
```bash
git clone [repositorio]
cd mod_agentes
source env_new/bin/activate
pip install -r requirements.txt
```

### Ejecución Local
```bash
# Configurar puerto (default 8000 para pruebas)
python3 app.py
```

## 🧪 Pruebas
Para probar el flujo completo con un ticket específico:
```bash
curl -X POST http://localhost:8000/znuny-webhook \
  -H "Content-Type: application/json" \
  -d '{"TicketID": [ID_DEL_TICKET]}'
```

---
*Desarrollado por el equipo de IA de Nexura Internacional S.A.S.*