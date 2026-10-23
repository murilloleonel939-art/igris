# IGRIS Chat — ventana de escritorio para Windows

Segundo ejecutable del proyecto. Muestra **solo la ventana del chat de IGRIS** con su avatar y su voz, sin abrir ningún explorador. Es independiente de `windows_agent/`, que sigue siendo el puente en segundo plano que ejecuta órdenes en el PC.

## Cómo se presenta al usuario

- Doble clic en el iniciador de Windows → aparece una ventana titulada **IGRIS** con el avatar y el chat.
- Sin barra de direcciones, sin pestañas, sin flechas, sin marcadores, sin menú del navegador.
- Se registra en `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, así que **arranca solo al iniciar sesión**.
- Cerrar la ventana cierra la aplicación: no queda nada corriendo en segundo plano.
- La ventana solo puede permanecer en `webigris.zottagroup.com`; cualquier enlace externo o ruta de administración se bloquea.

## Qué carga

El frontend ya publicado en `https://webigris.zottagroup.com`, la misma interfaz del explorador. Por eso este ejecutable **no requiere cambios en el backend ni en CORS**: el origen sigue siendo el que [server/main.py](../../server/main.py) ya acepta.

Consecuencia: necesita conexión a internet. Si más adelante se quiere sin conexión, hay que empaquetar `web/dist` dentro del ejecutable y añadir `tauri://localhost` a los orígenes permitidos en el backend.

## Dispositivos del equipo

Micrófono, altavoz y cámara se conceden automáticamente mediante
`--use-fake-ui-for-media-stream`, así que no aparece el diálogo de permisos del navegador. El audio automático queda habilitado con `--autoplay-policy=no-user-gesture-required`, para que la voz de Igris suene sin pulsar nada.

## Instalación y desinstalación

**Instalar**: doble clic en `IgrisChatSetup-v2.exe`. Se instala en el perfil del usuario, sin pedir administrador. Deja:

- `Inicio → IGRIS → IGRIS` (abrir el chat).
- `Inicio → IGRIS → Desinstalar IGRIS` (desinstalador visible, además del de Aplicaciones instaladas).
- Arranque automático al iniciar sesión, registrado en `HKCU\...\CurrentVersion\Run`.
- Entrada en **Configuración → Aplicaciones → Aplicaciones instaladas**.

**Desinstalar**: desde `Inicio → IGRIS → Desinstalar IGRIS`, o desde Aplicaciones instaladas. Los ganchos de [windows/hooks.nsh](src-tauri/windows/hooks.nsh) borran en este orden:

1. El valor `IGRIS` de la clave `Run` — sin esto, Windows intentaría abrir un ejecutable inexistente en cada inicio de sesión.
2. Los accesos directos del menú Inicio y del escritorio.
3. Los datos locales del WebView2 en `%LOCALAPPDATA%\com.zottagroup.igris.chat`, donde queda guardada **la clave de acceso y la sesión del usuario**. No deben sobrevivir a la desinstalación.
4. La carpeta de instalación si quedó vacía.

El workflow verifica estos ganchos en cada compilación: si alguien los rompe o los quita, el build falla en vez de publicar un instalador que deja basura en el PC.

## Compilación

El ejecutable **se compila en GitHub Actions**, no hace falta tener Rust ni Windows en local:

```
.github/workflows/build-windows-chat.yml
```

Se dispara al tocar `desktop/**`, a mano desde la pestaña Actions, o con un tag `chat-v*`. Genera:

- `desktop/output/IgrisChatSetup-v2.exe` → instalador NSIS, instalación por usuario, sin administrador.
- Copia automática a `web/public/downloads/IgrisChatSetup-v2.exe`.
- Commit del instalador en `main` y artifact descargable.

Para compilar en un Windows propio:

```powershell
cd desktop
npm install
npm run build
# Queda en src-tauri\target\release\bundle\nsis\
```

Requiere Rust estable, Visual Studio Build Tools con C++ y Node 20.

## Estructura

| Archivo | Función |
| --- | --- |
| `package.json` | Dependencias de la CLI de Tauri |
| `src-tauri/Cargo.toml` | Crate `igris-chat` |
| `src-tauri/tauri.conf.json` | Ventana, ícono, instalador NSIS y argumentos del WebView2 |
| `src-tauri/src/main.rs` | Arranque automático y bloqueo de navegación |
| `src-tauri/icons/` | Ícono generado desde `web/public/icons/icon-512.png` |
| `dist/index.html` | Pantalla de respaldo mientras carga el chat |
