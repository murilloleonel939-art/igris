#!/bin/bash

# Script para verificar y reparar el error de AttributeError en IGRIS
# Uso: bash verify_and_fix.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== VERIFICADOR DE IGRIS ===${NC}"
echo ""

# 1. Verificar que estamos en el directorio correcto
if [ ! -f "core/brain.py" ]; then
    echo -e "${RED}❌ Error: No se encontró core/brain.py${NC}"
    echo "Por favor, ejecuta este script desde la raíz del repositorio igris"
    exit 1
fi

echo -e "${GREEN}✓ Estructura de directorios correcta${NC}"

# 2. Verificar el error en brain.py
echo ""
echo -e "${YELLOW}Verificando core/brain.py...${NC}"

if grep -q "config.get_active_provider()" core/brain.py; then
    echo -e "${RED}❌ ENCONTRADO: config.get_active_provider() (INCORRECTO)${NC}"
    echo "   Línea(s) problemática(s):"
    grep -n "config.get_active_provider()" core/brain.py | sed 's/^/   /'
    NEEDS_FIX=true
else
    echo -e "${GREEN}✓ No se encontró config.get_active_provider()${NC}"
    NEEDS_FIX=false
fi

# 3. Verificar que existe get_active_provider_config() en config.py
echo ""
echo -e "${YELLOW}Verificando core/config.py...${NC}"

if grep -q "def get_active_provider_config" core/config.py; then
    echo -e "${GREEN}✓ Función get_active_provider_config() encontrada${NC}"
else
    echo -e "${RED}❌ Función get_active_provider_config() NO encontrada${NC}"
    echo "   Ejecuta: bash verify_and_fix.sh --fix-config"
    NEEDS_FIX_CONFIG=true
fi

# 4. Si necesita reparación
echo ""
if [ "$NEEDS_FIX" = true ]; then
    echo -e "${YELLOW}¿Deseas reparar automáticamente el problema? (s/n)${NC}"
    read -r response
    
    if [ "$response" = "s" ] || [ "$response" = "S" ]; then
        echo "Reparando core/brain.py..."
        
        # Backup del archivo original
        cp core/brain.py core/brain.py.backup
        echo -e "${GREEN}✓ Backup creado: core/brain.py.backup${NC}"
        
        # Reemplazar la línea problemática
        # Buscamos la línea exacta y la reemplazamos
        sed -i.bak 's/PROVIDER = config\.get_active_provider()/PROVIDER_CONFIG = config.get_active_provider_config()\nif PROVIDER_CONFIG:\n    PROVIDER = PROVIDER_CONFIG.get("active_provider", "nemotron")\nelse:\n    PROVIDER = "nemotron"/g' core/brain.py
        
        echo -e "${GREEN}✓ Cambio realizado${NC}"
        echo ""
        echo "Verificando el cambio:"
        grep -n "PROVIDER" core/brain.py | head -5 | sed 's/^/   /'
        
    else
        echo "Reparación cancelada."
        echo "Realiza los cambios manualmente según FIXES_REQUIRED.md"
    fi
else
    echo -e "${GREEN}✓ No se encontraron problemas en brain.py${NC}"
fi

# 5. Verificar git status
echo ""
echo -e "${YELLOW}Estado de Git:${NC}"
if git status --porcelain | grep -q "core/brain.py"; then
    echo -e "${YELLOW}⚠ Cambios sin commitear en core/brain.py${NC}"
    echo ""
    echo -e "${YELLOW}¿Deseas hacer commit de los cambios? (s/n)${NC}"
    read -r commit_response
    
    if [ "$commit_response" = "s" ] || [ "$commit_response" = "S" ]; then
        git add core/brain.py
        git commit -m "Fix: Cambiar get_active_provider() por get_active_provider_config() en brain.py"
        echo -e "${GREEN}✓ Cambios commiteados${NC}"
        
        echo ""
        echo -e "${YELLOW}¿Deseas hacer push a GitHub? (s/n)${NC}"
        read -r push_response
        
        if [ "$push_response" = "s" ] || [ "$push_response" = "S" ]; then
            git push origin main
            echo -e "${GREEN}✓ Cambios pusheados a GitHub${NC}"
            echo ""
            echo -e "${YELLOW}Próximo paso: Redeploy en Coolify${NC}"
            echo "1. Ve a tu servicio backend en Coolify"
            echo "2. Haz clic en 'Rebuild and Deploy'"
            echo "3. Espera 2-3 minutos"
        fi
    fi
else
    echo -e "${GREEN}✓ No hay cambios sin guardar${NC}"
fi

# 6. Resumen final
echo ""
echo -e "${GREEN}=== VERIFICACIÓN COMPLETADA ===${NC}"
echo ""
echo "Resumen:"
echo "  • core/brain.py: $([ "$NEEDS_FIX" = false ] && echo 'OK' || echo 'REPARADO')"
echo "  • core/config.py: $([ -z "$NEEDS_FIX_CONFIG" ] && echo 'OK' || echo 'REQUIERE ATENCIÓN')"
echo ""
echo "Próximos pasos:"
echo "  1. Verifica los cambios con: git diff core/brain.py"
echo "  2. Si todo se ve bien, push a GitHub"
echo "  3. Redeploy en Coolify"
echo "  4. Verifica que el contenedor inicia sin errores"
