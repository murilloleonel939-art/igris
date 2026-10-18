# Agente local de IGRIS para Windows

El agente se conecta hacia el backend por WebSocket seguro. El PC debe estar encendido; al apagarlo se desconecta y al iniciar sesión vuelve a conectarse.

## Instalación sencilla

Descarga `igris-agent-install-v6.ps1` desde el menú **Agente Windows** del panel de IGRIS y ejecútalo con PowerShell. El archivo es autocontenido: no descarga código desde GitHub. También puedes abrir directamente `/downloads/igris-agent-install-v6.ps1` en tu instalación de IGRIS.

El instalador usa automáticamente `wss://igris.zottagroup.com/api/device/ws` y solo te pedirá el `NODE_TOKEN` individual generado desde el panel. Instalará Python automáticamente si Windows tiene `winget`, instalará la dependencia y configurará el inicio automático.

## Instalación sin PowerShell
La versión ejecutable se distribuye como `IgrisAgentSetup-v7.exe`. Ábrela, pega el `NODE_TOKEN` generado en **Panel admin → Conexiones → Agente Windows** y finaliza. El agente queda en segundo plano y arranca automáticamente con Windows. Para quitarlo, ve a **Configuración → Aplicaciones → Aplicaciones instaladas → IGRIS Windows Agent → Desinstalar**. El desinstalador elimina el agente, el arranque automático y el token guardado.

Para compilarlo en Windows:

```powershell
.\build-exe.ps1
# Abre igris-agent.iss con Inno Setup y compílalo
```

## Instalación manual

1. Instala Python 3.11+ en Windows.
2. Abre PowerShell en esta carpeta y ejecuta `py -m pip install websockets`.
3. Define estas variables:

```powershell
$env:IGRIS_DEVICE_URL = "wss://igris.zottagroup.com/api/device/ws"
$env:NODE_TOKEN = "EL_TOKEN_INDIVIDUAL_GENERADO_EN_EL_PANEL"
```

4. Ejecuta `py agent.py` y verifica que aparezca `Agente local IGRIS conectado`.
5. Para conectarlo al inicio de Windows, crea una tarea del Programador de tareas que ejecute `py C:\ruta\windows_agent\agent.py` al iniciar sesión, con el mismo entorno configurado de forma segura.

Cada agente debe usar un token individual generado desde el panel. El administrador puede regenerarlo o revocarlo; al revocarlo, el agente pierde el acceso. El token debe mantenerse secreto. El agente solo acepta acciones cerradas: abrir URLs http/https, multimedia, volumen y tres programas autorizados. No ejecuta comandos recibidos desde la nube.
