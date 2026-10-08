/**
 * IGRIS Frontend Server
 * Sirve los archivos compilados desde /dist y devuelve index.html en las rutas
 * de la SPA (para que Vue Router funcione al recargar o al abrir /u directo).
 * También hace de proxy de /api y /auth hacia el backend.
 */

import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import http from 'http';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();

// La CSP tiene que coincidir con la de web/index.html. Si aquí falta un
// directivo, el navegador aplica la MÁS restrictiva de las dos y la PWA deja
// de funcionar en producción aunque en local sí funcione.
app.use((req, res, next) => {
  res.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data: blob:; media-src 'self' blob:; " +
      "connect-src 'self' https://igris.zottagroup.com http://localhost:8000 http://127.0.0.1:8000; " +
      "worker-src 'self'; manifest-src 'self';"
  );
  next();
});

const PORT = process.env.PORT || 3000;

// Backend URL para proxy interno (siempre localhost:8000, no usar VITE_API_URL)
const BACKEND_URL = 'http://localhost:8000';

// Parse backend URL (siempre localhost)
let backendHost = 'localhost';
let backendPort = 8000;

try {
  const url = new URL(BACKEND_URL);
  backendHost = url.hostname || 'localhost';
  backendPort = url.port ? parseInt(url.port, 10) : 8000;
} catch (e) {
  console.error('Error parsing BACKEND_URL:', e);
}

// Proxy function: redirige /api y /auth al backend
function proxyToBackend(req, res) {
  // OJO: hay que usar req.originalUrl, no req.url.
  // Al montar app.use('/api', ...) Express recorta el prefijo, así que req.url
  // llega ya sin él ("/auth/check") y el backend respondería 404. originalUrl
  // conserva la ruta completa tal como la pidió el navegador.
  const options = {
    hostname: backendHost,
    port: backendPort,
    path: req.originalUrl,
    method: req.method,
    headers: {
      ...req.headers,
      host: backendHost
    }
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err);
    res.status(502).json({ error: 'Bad Gateway' });
  });

  req.pipe(proxyReq);
}

/**
 * El service worker NO se puede cachear nunca.
 *
 * Si el navegador guarda sw.js, sigue ejecutando la versión antigua y los
 * usuarios no reciben las actualizaciones de la aplicación: se quedan con la
 * copia en caché indefinidamente. Esta ruta va antes del static para que gane.
 * Service-Worker-Allowed permite que el worker controle todo el sitio aunque
 * el archivo esté en la raíz (scope "/").
 */
app.get('/sw.js', (req, res) => {
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.setHeader('Service-Worker-Allowed', '/');
  res.setHeader('Content-Type', 'application/javascript; charset=utf-8');
  res.sendFile(join(__dirname, 'dist', 'sw.js'));
});

/**
 * Los DOS manifests de la PWA.
 *
 * Son aplicaciones instalables distintas: la del administrador tiene que abrir
 * en /acceso y la de los usuarios en /u/login. El navegador decide cuál usa
 * leyendo el <link rel="manifest"> del HTML, así que lo único que hace falta es
 * servir un index.html con el enlace correcto en cada caso. El mismo archivo
 * index.html vale para las dos: aquí solo se cambia ese enlace.
 */
const MANIFEST_ADMIN = '/manifest-admin.webmanifest';
const MANIFEST_USER = '/manifest.webmanifest';

function isUserPath(pathname) {
  return pathname === '/u' || pathname.startsWith('/u/');
}

/**
 * Devuelve el index.html con el manifest que corresponde a la ruta.
 *
 * Se lee el archivo en cada petición a propósito: son solo unas pocas (una por
 * navegación, no por recurso) y así al volver a compilar en local nunca se
 * sirve una copia antigua en memoria.
 */
function renderIndex(pathname) {
  const html = fs.readFileSync(join(__dirname, 'dist', 'index.html'), 'utf8');

  // Las rutas de usuarios (/u y /u/login) llevan el manifest de usuarios; todo
  // lo demás (/, /config, /panel/usuarios, /acceso) es del administrador.
  if (isUserPath(pathname)) {
    return html
      .replace(`href="${MANIFEST_ADMIN}"`, `href="${MANIFEST_USER}"`)
      .replace('content="IGRIS Admin"', 'content="IGRIS"');
  }
  return html;
}

function sendIndex(req, res) {
  try {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    // Sin caché: si el navegador guardara este HTML se quedaría con el enlace
    // al manifest equivocado, y al instalar la app abriría en el área que no es.
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.send(renderIndex(req.path));
  } catch (err) {
    console.error('No se pudo servir index.html:', err);
    res.status(500).send('Error interno');
  }
}

// Proxy rutas API y auth hacia el backend
app.use('/api', proxyToBackend);
app.use('/auth', proxyToBackend);

// Servir archivos estáticos desde dist.
// index: false -> que NO sirva index.html por su cuenta; de eso se encarga
// sendIndex, que además inyecta el manifest correcto.
app.use(
  express.static(join(__dirname, 'dist'), {
    index: false,
    setHeaders(res, filePath) {
      // El tipo MIME del manifest importa: si no es application/manifest+json
      // (o application/json), el navegador lo ignora y la app no es instalable.
      if (filePath.endsWith('.webmanifest')) {
        res.setHeader('Content-Type', 'application/manifest+json; charset=utf-8');
      }
    }
  })
);

// Rutas de la SPA: cualquier cosa que no sea un archivo estático devuelve el
// index.html (para que Vue Router funcione al recargar o al abrir /u directo).
app.get('*', sendIndex);

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 IGRIS Frontend corriendo en puerto ${PORT}`);
  console.log(`📍 URL: http://0.0.0.0:${PORT}`);
  console.log(`🔗 Backend proxy: ${backendHost}:${backendPort}`);
});
