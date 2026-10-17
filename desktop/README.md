# Igris para PC

Aplicación de escritorio para usuarios. Abre directamente el acceso de usuario y permite únicamente la navegación bajo `/u`; las rutas administrativas se bloquean y se abren fuera de la aplicación.

## Desarrollo

```bash
cd desktop
npm install
npm start
```

## Ejecutable de Windows

El empaquetado debe ejecutarse en Windows:

```bash
npm run dist
```

Genera un ejecutable portable en `desktop/dist/`.

La compilación desde Linux requiere Wine para generar el artefacto de Windows. La aplicación usa la versión publicada de `webigris.zottagroup.com`, por lo que no duplica el backend ni el panel administrativo.
