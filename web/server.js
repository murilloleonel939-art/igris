/**
 * IGRIS Frontend Server
 * Sirve archivos estáticos desde /dist y redirige rutas a index.html (SPA)
 */

import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

// Servir archivos estáticos desde dist
app.use(express.static(join(__dirname, 'dist')));

// Redirigir todas las rutas a index.html (para que Vue Router funcione)
app.get('*', (req, res) => {
  res.sendFile(join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 IGRIS Frontend corriendo en puerto ${PORT}`);
  console.log(`📍 URL: http://0.0.0.0:${PORT}`);
});
