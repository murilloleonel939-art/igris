/**
 * IGRIS Frontend Server
 * Sirve archivos estáticos desde /dist y redirige rutas a index.html (SPA)
 * También hace proxy de /api y /auth hacia el backend
 */

import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import http from 'http';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Backend URL para proxy interno (siempre localhost:8000, no usar VITE_API_URL)
const BACKEND_URL = 'http://localhost:8000';

// Parse backend URL (siempre localhost)
let backendHost = 'localhost';
let backendPort = 8000;
let backendPath = '/';

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