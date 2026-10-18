# Agente local de IGRIS para Windows

El agente se conecta hacia el backend por WebSocket seguro. El PC debe estar encendido; al apagarlo se desconecta y al iniciar sesión vuelve a conectarse.

## Instalación sencilla

Descarga `igris-agent-install.ps1` desde el menú **Agente Windows** del panel de IGRIS y ejecútalo con PowerShell. El archivo es autocontenido: no descarga código desde GitHub. También puedes abrir directamente `/downloads/igris-agent-install.ps1` en tu instalación de IGRIS.

El instalador te pedirá la URL WebSocket y el `NODE_TOKEN`, instalará Python automáticamente si Windows tiene `winget`, instalará la dependencia y configurará el inicio automático.

## Instalación manual

1. Instala Python 3.11+ en Windows.
2. Abre PowerShell en esta carpeta y ejecuta `py -m pip install websockets`.
3. Define estas variables:

```powershell
$env:IGRIS_DEVICE_URL = "wss://TU-DOMINIO/api/device/ws"
$env:NODE_TOKEN = "EL_MISMO_TOKEN_NODE_TOKEN_DEL_BACKEND"
```

4. Ejecuta `py agent.py` y verifica que aparezca `Agente local IGRIS conectado`.
5. Para conectarlo al inicio de Windows, crea una tarea del Programador de tareas que ejecute `py C:\ruta\windows_agent\agent.py` al iniciar sesión, con el mismo entorno configurado de forma segura.

El backend usa `NODE_TOKEN` para autenticar este primer agente. Debe mantenerse secreto. El agente solo acepta acciones cerradas: abrir URLs http/https, multimedia, volumen y tres programas autorizados. No ejecuta comandos recibidos desde la nube.
