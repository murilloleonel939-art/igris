# Agente local de IGRIS para Windows

El agente se conecta hacia el backend por WebSocket seguro. El PC debe estar encendido; al apagarlo se desconecta y al iniciar sesión vuelve a conectarse.

## Instalación desde el ejecutable
Descarga `IgrisAgentSetup-v11.exe` desde **Panel admin → Conexiones → Agente Windows**. Haz doble clic, pega el `NODE_TOKEN` individual del equipo y termina el asistente. El agente queda en segundo plano y arranca automáticamente con Windows. En **Inicio → IGRIS Windows Agent** encontrarás el agente y **Configurar IGRIS** permite cambiar el token sin desinstalar. Crea archivos Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), texto (`.txt`) y CSV directamente en la carpeta Documentos del PC; el servidor no guarda copias. Para quitarlo, ve a **Configuración → Aplicaciones → Aplicaciones instaladas → IGRIS Windows Agent → Desinstalar**; se borra también el token local.

Para compilarlo en Windows:

```powershell
.\build-exe.ps1
# Compila primero agent.py y después abre igris-agent.iss con Inno Setup
# El instalador genera output\IgrisAgentSetup-v11.exe
# La compilación incluye Tkinter para Configurar IGRIS
```

## Instalación manual

1. Instala Python 3.11+ en Windows.
2. Abre PowerShell en esta carpeta y ejecuta `py -m pip install -r requirements.txt`.
3. Define estas variables:

```powershell
$env:IGRIS_DEVICE_URL = "wss://igris.zottagroup.com/api/device/ws"
$env:NODE_TOKEN = "EL_TOKEN_INDIVIDUAL_GENERADO_EN_EL_PANEL"
```

4. Ejecuta `py agent.py` y verifica que aparezca `Agente local IGRIS conectado`.
5. Para conectarlo al inicio de Windows, crea una tarea del Programador de tareas que ejecute `py C:\ruta\windows_agent\agent.py` al iniciar sesión, con el mismo entorno configurado de forma segura.

Cada agente debe usar un token individual generado desde el panel. El administrador puede regenerarlo o revocarlo; al revocarlo, el agente pierde el acceso. El token debe mantenerse secreto. Para cambiarlo sin reinstalar, abre **Inicio → IGRIS Windows Agent → Configurar IGRIS**, pega el nuevo valor y pulsa **Guardar**; el agente se reinicia automáticamente. La configuración guardada en `%LOCALAPPDATA%\IGRIS\node_token.txt` tiene prioridad sobre una variable `NODE_TOKEN` antigua. El agente solo acepta acciones cerradas: abrir URLs http/https, multimedia, volumen y tres programas autorizados. No ejecuta comandos recibidos desde la nube.
