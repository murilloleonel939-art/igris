# Igris para PC

Aplicación de escritorio para usuarios. Abre directamente el acceso de usuario y permite únicamente la navegación bajo `/u`; las rutas administrativas se bloquean y se abren fuera de la aplicación.

## Desarrollo

Instala primero Python 3.10+ y las dependencias de voz:

```bash
cd desktop
python -m pip install -r requirements.txt
npm install
npm start
```

La aplicación muestra el botón **Voz local**. Captura directamente del micrófono, detecta el silencio, transcribe con `faster-whisper` y coloca la orden transcrita en el chat. El primer uso descarga el modelo Whisper configurado; por defecto es `small`. Puedes usar `IGRIS_WHISPER_MODEL=base` en equipos modestos.

## Ejecutable de Windows

El empaquetado debe ejecutarse en Windows:

```bash
npm run dist
```

Genera un ejecutable portable en `desktop/dist/`.

La compilación desde Linux requiere Wine para generar el artefacto de Windows. La aplicación usa la versión publicada de `webigris.zottagroup.com`, por lo que no duplica el backend ni el panel administrativo.
