#!/bin/bash
# Script para subir cambios a GitHub y forzar redeploy en Coolify

set -e

echo "🚀 Sincronizando con GitHub..."

# Variables
# El token NO va escrito aquí: este archivo se sube al repositorio y cualquiera
# con acceso al código podría usarlo para escribir en nombre de la cuenta.
# Se lee de la variable de entorno GITHUB_TOKEN (o GITHUB_PAT).
PAT="${GITHUB_TOKEN:-${GITHUB_PAT:-}}"
if [ -z "$PAT" ]; then
  echo "❌ Falta la variable de entorno GITHUB_TOKEN."
  echo "   Ejemplo:  GITHUB_TOKEN=github_pat_xxx ./push_to_github.sh"
  exit 1
fi
REPO_URL="https://${PAT}@github.com/murilloleonel939-art/igris.git"
BRANCH="main"

# Configurar git
git config --global user.email "igris@bot.local"
git config --global user.name "IGRIS Bot"

# Agregar cambios
echo "📝 Agregando cambios..."
git add requirements.txt server/main.py

# Verificar que hay cambios
if git diff --cached --quiet; then
    echo "⚠️  No hay cambios para hacer commit"
    exit 0
fi

# Commit
echo "💾 Haciendo commit..."
git commit -m "fix: add python-multipart and use Body() for JSON endpoints"

# Push
echo "⬆️  Subiendo a GitHub..."
git push $REPO_URL $BRANCH

echo "✅ ¡Listo! Los cambios están en GitHub."
echo "📦 Coolify debería re-descargar y deployar automáticamente."
echo ""
echo "Si no re-deploya automáticamente:"
echo "  1. Abre https://igris.zottagroup.com (Coolify)"
echo "  2. Ve a la aplicación IGRIS"
echo "  3. Haz clic en 'Redeploy' o 'Rebuild'"
