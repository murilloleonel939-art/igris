#!/usr/bin/env node
/**
 * GitHub Push Script
 * Sube todos los archivos a GitHub usando la GitHub API
 */

const https = require('https');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

// Configuración
// El token NO va escrito aquí: este archivo se sube al repositorio y cualquiera
// con acceso al código podría usarlo para escribir en nombre de la cuenta.
// Se lee de la variable de entorno GITHUB_TOKEN.
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
if (!GITHUB_TOKEN) {
  console.error('❌ Falta la variable de entorno GITHUB_TOKEN.');
  console.error('   Ejemplo:  GITHUB_TOKEN=github_pat_xxx node push-to-github.js');
  process.exit(1);
}
const REPO_OWNER = 'murilloleonel939-art';
const REPO_NAME = 'igris';
const BRANCH = 'main';
const COMMIT_MESSAGE = 'feat: Frontend Vue 3 build + Coolify deployment ready\n\n- Added web/server.js (Express server)\n- Added web/.env.production (production config)\n- Built web/dist/ (production bundle)\n- Added Dockerfile.frontend\n- Added comprehensive deployment documentation\n- All 25+ verification checks passed';

// Raíz del proyecto. Por defecto, la carpeta donde está este script (así
// funciona en cualquier máquina); se puede cambiar con PROJECT_ROOT=...
const PROJECT_ROOT = process.env.PROJECT_ROOT || __dirname;

// Archivos a subir
const FILES_TO_UPLOAD = [
  'web/server.js',
  'web/.env.production',
  'web/dist/index.html',
  'web/dist/assets/index-6179ee8c.css',
  'web/dist/assets/index-1d55c3fb.js',
  'web/package.json',
  'Dockerfile.frontend',
  'COOLIFY_DEPLOY.md',
  'FRONTEND_DEPLOYMENT.md',
  'COOLIFY_STEP_BY_STEP.md',
  'DEPLOYMENT_SUMMARY_OCT2024.md',
  'DEPLOYMENT_COMPLETE.txt',
  'verify_deployment.sh',
  'push-to-github.js'
];

console.log('🚀 IGRIS GitHub Push Script');
console.log('=' .repeat(50));
console.log(`Repository: ${REPO_OWNER}/${REPO_NAME}`);
console.log(`Branch: ${BRANCH}`);
console.log(`Files: ${FILES_TO_UPLOAD.length}`);
console.log('=' .repeat(50));

// Helper para hacer requests HTTPS
function httpsRequest(options, data = null) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const response = {
            status: res.statusCode,
            headers: res.headers,
            body: body ? JSON.parse(body) : null
          };
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(response);
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${body}`));
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

// Obtener última commit
async function getLastCommit() {
  console.log('\n📍 Obteniendo última commit...');
  const options = {
    hostname: 'api.github.com',
    path: `/repos/${REPO_OWNER}/${REPO_NAME}/commits/${BRANCH}`,
    method: 'GET',
    headers: {
      'Authorization': `token ${GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'IGRIS-Deployment'
    }
  };

  try {
    const res = await httpsRequest(options);
    console.log(`✅ SHA: ${res.body.sha.substring(0, 7)}`);
    return res.body.sha;
  } catch (e) {
    console.error('❌ Error:', e.message);
    throw e;
  }
}

// Crear árbol de cambios
async function createTree(baseSha) {
  console.log('\n🌳 Creando árbol de cambios...');
  
  const tree = [];
  
  for (const file of FILES_TO_UPLOAD) {
    const filePath = path.join(PROJECT_ROOT, file);
    
    if (!fs.existsSync(filePath)) {
      console.log(`⚠️  Saltando ${file} (no existe)`);
      continue;
    }

    const content = fs.readFileSync(filePath, 'utf-8');
    const mode = file.endsWith('.sh') ? '100755' : '100644';
    
    tree.push({
      path: file,
      mode: mode,
      type: 'blob',
      content: content
    });
    console.log(`✅ ${file}`);
  }

  const options = {
    hostname: 'api.github.com',
    path: `/repos/${REPO_OWNER}/${REPO_NAME}/git/trees`,
    method: 'POST',
    headers: {
      'Authorization': `token ${GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'IGRIS-Deployment',
      'Content-Type': 'application/json'
    }
  };

  const payload = JSON.stringify({
    base_tree: baseSha,
    tree: tree
  });

  try {
    const res = await httpsRequest(options, payload);
    console.log(`✅ Árbol creado: ${res.body.sha.substring(0, 7)}`);
    return res.body.sha;
  } catch (e) {
    console.error('❌ Error:', e.message);
    throw e;
  }
}

// Crear commit
async function createCommit(treeSha, parentSha) {
  console.log('\n📝 Creando commit...');
  
  const options = {
    hostname: 'api.github.com',
    path: `/repos/${REPO_OWNER}/${REPO_NAME}/git/commits`,
    method: 'POST',
    headers: {
      'Authorization': `token ${GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'IGRIS-Deployment',
      'Content-Type': 'application/json'
    }
  };

  const payload = JSON.stringify({
    message: COMMIT_MESSAGE,
    tree: treeSha,
    parents: [parentSha],
    author: {
      name: 'IGRIS Bot',
      email: 'igris@zottagroup.com',
      date: new Date().toISOString()
    }
  });

  try {
    const res = await httpsRequest(options, payload);
    console.log(`✅ Commit creado: ${res.body.sha.substring(0, 7)}`);
    return res.body.sha;
  } catch (e) {
    console.error('❌ Error:', e.message);
    throw e;
  }
}

// Actualizar referencia
async function updateRef(commitSha) {
  console.log('\n🔄 Actualizando referencia...');
  
  const options = {
    hostname: 'api.github.com',
    path: `/repos/${REPO_OWNER}/${REPO_NAME}/git/refs/heads/${BRANCH}`,
    method: 'PATCH',
    headers: {
      'Authorization': `token ${GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'IGRIS-Deployment',
      'Content-Type': 'application/json'
    }
  };

  const payload = JSON.stringify({
    sha: commitSha,
    force: false
  });

  try {
    const res = await httpsRequest(options, payload);
    console.log(`✅ Rama actualizada: ${res.body.ref}`);
    return res.body.object.sha;
  } catch (e) {
    console.error('❌ Error:', e.message);
    throw e;
  }
}

// Main
async function main() {
  try {
    const lastCommit = await getLastCommit();
    const treeSha = await createTree(lastCommit);
    const newCommit = await createCommit(treeSha, lastCommit);
    const finalRef = await updateRef(newCommit);
    
    console.log('\n' + '='.repeat(50));
    console.log('✅ PUSH COMPLETADO CON ÉXITO');
    console.log('='.repeat(50));
    console.log(`\n📍 Nuevo commit: ${newCommit.substring(0, 7)}`);
    console.log(`🔗 Ver en GitHub: https://github.com/${REPO_OWNER}/${REPO_NAME}/commit/${newCommit}`);
    console.log(`\n🚀 Ahora puedes hacer redeploy en Coolify\n`);
    
  } catch (error) {
    console.error('\n❌ ERROR:', error.message);
    process.exit(1);
  }
}

main();
