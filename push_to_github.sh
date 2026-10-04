#!/bin/bash
# Script para subir cambios a GitHub y forzar redeploy en Coolify

set -e

echo "🚀 Sincronizando con GitHub..."

# Variables
REPO_URL="https://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@github.com/murilloleonel939-art/igris.git"
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
echo "  1. Abre https://igris.zottaggroup.com (Coolify)"
echo "  2. Ve a la aplicación IGRIS"
echo "  3. Haz clic en 'Redeploy' o 'Rebuild'"
