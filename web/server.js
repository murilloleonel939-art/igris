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
  const options = {
    hostname: backendHost,
    port: backendPort,
    path: req.url,
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

// Proxy rutas API y auth hacia el backend
app.use('/api', proxyToBackend);
app.use('/auth', proxyToBackend);

// Servir archivos estáticos desde dist
app.use(express.static(join(__dirname, 'dist')));

// Redirigir todas las rutas restantes a index.html (para que Vue Router funcione)
app.get('*', (req, res) => {
  res.sendFile(join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 IGRIS Frontend corriendo en puerto ${PORT}`);
  console.log(`📍 URL: http://0.0.0.0:${PORT}`);
  console.log(`🔗 Backend proxy: ${backendHost}:${backendPort}`);
});
