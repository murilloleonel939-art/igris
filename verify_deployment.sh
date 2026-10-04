#!/bin/bash
# IGRIS Deployment Verification Script
# Verifica que todo esté listo para deployarse en Coolify

set -e

echo "🔍 IGRIS Deployment Verification"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_mark() {
    echo -e "${GREEN}✅${NC} $1"
}

error_mark() {
    echo -e "${RED}❌${NC} $1"
}

warning_mark() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Change to project root
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)

echo "📂 Project Root: $PROJECT_ROOT"
echo ""

# ============== BACKEND CHECKS ==============
echo "📊 BACKEND CHECKS"
echo "-----------------"

if [ -f "server/main.py" ]; then
    check_mark "server/main.py exists"
else
    error_mark "server/main.py NOT found"
fi

if [ -f "requirements.txt" ]; then
    check_mark "requirements.txt exists"
else
    error_mark "requirements.txt NOT found"
fi

if grep -q "CORSMiddleware" server/main.py; then
    check_mark "CORS middleware configured in backend"
else
    error_mark "CORS NOT configured in backend"
fi

if [ -f "Dockerfile" ]; then
    check_mark "Backend Dockerfile exists"
else
    error_mark "Backend Dockerfile NOT found"
fi

echo ""

# ============== FRONTEND CHECKS ==============
echo "📦 FRONTEND CHECKS"
echo "------------------"

# package.json
if [ -f "web/package.json" ]; then
    check_mark "web/package.json exists"
    
    if grep -q "express" web/package.json; then
        check_mark "Express in dependencies"
    else
        error_mark "Express NOT in dependencies"
    fi
    
    if grep -q '"start"' web/package.json; then
        check_mark "npm start script configured"
    else
        error_mark "npm start script NOT configured"
    fi
    
    if grep -q '"build"' web/package.json; then
        check_mark "npm build script configured"
    else
        error_mark "npm build script NOT configured"
    fi
else
    error_mark "web/package.json NOT found"
fi

# server.js
if [ -f "web/server.js" ]; then
    check_mark "web/server.js exists"
    
    if grep -q "express" web/server.js; then
        check_mark "server.js imports express"
    else
        error_mark "server.js does NOT import express"
    fi
    
    if grep -q "dist" web/server.js; then
        check_mark "server.js serves /dist/"
    else
        error_mark "server.js does NOT serve /dist/"
    fi
    
    node -c web/server.js 2>/dev/null && check_mark "server.js is syntactically valid" || error_mark "server.js has syntax errors"
else
    error_mark "web/server.js NOT found"
fi

# .env.production
if [ -f "web/.env.production" ]; then
    check_mark "web/.env.production exists"
    
    if grep -q "VITE_API_URL" web/.env.production; then
        check_mark "VITE_API_URL defined in .env.production"
        VITE_API=$(grep "VITE_API_URL" web/.env.production)
        echo "         → $VITE_API"
    else
        error_mark "VITE_API_URL NOT defined in .env.production"
    fi
else
    error_mark "web/.env.production NOT found"
fi

# dist/ folder
if [ -d "web/dist" ]; then
    check_mark "web/dist/ exists (frontend built)"
    
    FILE_COUNT=$(find web/dist -type f | wc -l)
    TOTAL_SIZE=$(du -sh web/dist | cut -f1)
    echo "         → $FILE_COUNT files, $TOTAL_SIZE total"
    
    if [ -f "web/dist/index.html" ]; then
        check_mark "web/dist/index.html (main entry point)"
    else
        error_mark "web/dist/index.html NOT found"
    fi
else
    error_mark "web/dist/ NOT found - need to run: npm run build"
fi

# Vue components
if [ -f "web/src/pages/Login.vue" ]; then
    check_mark "web/src/pages/Login.vue exists"
else
    error_mark "Login.vue NOT found"
fi

if [ -f "web/src/pages/Dashboard.vue" ]; then
    check_mark "web/src/pages/Dashboard.vue exists"
else
    error_mark "Dashboard.vue NOT found"
fi

if [ -f "web/src/api.js" ]; then
    check_mark "web/src/api.js exists"
    
    if grep -q "VITE_API_URL" web/src/api.js; then
        check_mark "api.js uses VITE_API_URL environment variable"
    else
        error_mark "api.js does NOT use VITE_API_URL"
    fi
else
    error_mark "web/src/api.js NOT found"
fi

# Docker frontend
if [ -f "Dockerfile.frontend" ]; then
    check_mark "Dockerfile.frontend exists"
else
    warning_mark "Dockerfile.frontend NOT found (optional)"
fi

echo ""

# ============== DOCUMENTATION CHECKS ==============
echo "📚 DOCUMENTATION CHECKS"
echo "----------------------"

DOCS=(
    "README.md"
    "WEB_SETUP.md"
    "COOLIFY_DEPLOY.md"
    "FRONTEND_DEPLOYMENT.md"
    "DEPLOYMENT_SUMMARY_OCT2024.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        check_mark "$doc exists"
    else
        warning_mark "$doc NOT found"
    fi
done

echo ""

# ============== FINAL SUMMARY ==============
echo "📋 DEPLOYMENT READINESS"
echo "----------------------"

BACKEND_READY=true
FRONTEND_READY=true

[ -f "server/main.py" ] || BACKEND_READY=false
[ -f "requirements.txt" ] || BACKEND_READY=false
[ -f "Dockerfile" ] || BACKEND_READY=false

[ -f "web/package.json" ] || FRONTEND_READY=false
[ -f "web/server.js" ] || FRONTEND_READY=false
[ -f "web/.env.production" ] || FRONTEND_READY=false
[ -d "web/dist" ] || FRONTEND_READY=false

echo ""
if [ "$BACKEND_READY" = true ]; then
    check_mark "BACKEND: Ready for deployment"
else
    error_mark "BACKEND: Missing files"
fi

if [ "$FRONTEND_READY" = true ]; then
    check_mark "FRONTEND: Ready for deployment"
else
    error_mark "FRONTEND: Missing files or build incomplete"
fi

echo ""

if [ "$BACKEND_READY" = true ] && [ "$FRONTEND_READY" = true ]; then
    echo -e "${GREEN}✅ IGRIS IS READY FOR COOLIFY DEPLOYMENT${NC}"
    echo ""
    echo "📝 Next Steps:"
    echo "  1. git add -A && git commit -m 'feat: Frontend build ready' && git push"
    echo "  2. Create new app in Coolify (Node.js, /web directory)"
    echo "  3. Configure environment: VITE_API_URL=https://igris.zottagroup.com"
    echo "  4. Deploy!"
    exit 0
else
    echo -e "${RED}❌ IGRIS IS NOT YET READY FOR DEPLOYMENT${NC}"
    echo ""
    echo "⚠️ Missing components:"
    [ "$FRONTEND_READY" = false ] && echo "  - Frontend build missing or incomplete"
    [ "$BACKEND_READY" = false ] && echo "  - Backend files missing"
    exit 1
fi
