#!/usr/bin/env bash
# ==============================================================================
# GridWise API Endpoint Verification Script
# Tests GET /health and POST /optimize-energy against running service
# ==============================================================================
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
# Strip trailing slash if present
BASE_URL="${BASE_URL%/}"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE} Testing GridWise API Endpoints: ${BASE_URL}${NC}"
echo -e "${BLUE}======================================================${NC}"

# ──────────────────────────────────────────────────────────────────────────────
# Test 1: GET /health
# ──────────────────────────────────────────────────────────────────────────────
echo -e "\n${BLUE}[1/2] Checking GET /health ...${NC}"

HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${BASE_URL}/health" --connect-timeout 5)
HTTP_CODE=$(echo "${HEALTH_RESPONSE}" | tail -n1)
BODY=$(echo "${HEALTH_RESPONSE}" | sed '$d')

if [ "${HTTP_CODE}" -eq 200 ] && echo "${BODY}" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    echo -e "${GREEN}✓ Health Check Passed! HTTP 200 OK${NC}"
    echo "  Response: ${BODY}"
else
    echo -e "${RED}✗ Health Check Failed! HTTP Status: ${HTTP_CODE}${NC}"
    echo "  Response: ${BODY}"
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# Test 2: POST /optimize-energy
# ──────────────────────────────────────────────────────────────────────────────
echo -e "\n${BLUE}[2/2] Checking POST /optimize-energy ...${NC}"

PAYLOAD=$(cat << 'EOF'
{
  "scenario_id": "CURL-VERIFY-01",
  "operator_notes": [
    "Solar output will drop to 20% from 1 PM to 3 PM due to cleaning.",
    "Do not charge battery between 2 PM and 4 PM."
  ],
  "hours": [
    {"hour": 0, "demand_kwh": 60, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 1, "demand_kwh": 55, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 2, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 3, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 4, "demand_kwh": 55, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 5, "demand_kwh": 70, "solar_kwh": 5, "tariff_bdt_per_kwh": 6},
    {"hour": 6, "demand_kwh": 90, "solar_kwh": 20, "tariff_bdt_per_kwh": 7},
    {"hour": 7, "demand_kwh": 120, "solar_kwh": 45, "tariff_bdt_per_kwh": 8},
    {"hour": 8, "demand_kwh": 150, "solar_kwh": 80, "tariff_bdt_per_kwh": 9},
    {"hour": 9, "demand_kwh": 170, "solar_kwh": 110, "tariff_bdt_per_kwh": 9},
    {"hour": 10, "demand_kwh": 180, "solar_kwh": 130, "tariff_bdt_per_kwh": 10},
    {"hour": 11, "demand_kwh": 190, "solar_kwh": 140, "tariff_bdt_per_kwh": 10},
    {"hour": 12, "demand_kwh": 200, "solar_kwh": 145, "tariff_bdt_per_kwh": 11},
    {"hour": 13, "demand_kwh": 195, "solar_kwh": 30, "tariff_bdt_per_kwh": 11},
    {"hour": 14, "demand_kwh": 185, "solar_kwh": 28, "tariff_bdt_per_kwh": 12},
    {"hour": 15, "demand_kwh": 175, "solar_kwh": 100, "tariff_bdt_per_kwh": 10},
    {"hour": 16, "demand_kwh": 160, "solar_kwh": 70, "tariff_bdt_per_kwh": 9},
    {"hour": 17, "demand_kwh": 140, "solar_kwh": 35, "tariff_bdt_per_kwh": 8},
    {"hour": 18, "demand_kwh": 130, "solar_kwh": 10, "tariff_bdt_per_kwh": 7},
    {"hour": 19, "demand_kwh": 120, "solar_kwh": 0, "tariff_bdt_per_kwh": 7},
    {"hour": 20, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 21, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
    {"hour": 22, "demand_kwh": 70, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
    {"hour": 23, "demand_kwh": 65, "solar_kwh": 0, "tariff_bdt_per_kwh": 5}
  ],
  "battery": {
    "capacity_kwh": 200,
    "initial_energy_kwh": 100,
    "minimum_energy_kwh": 40,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50
  }
}
EOF
)

OPTIMIZE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/optimize-energy" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" \
  --connect-timeout 10)

OPT_CODE=$(echo "${OPTIMIZE_RESPONSE}" | tail -n1)
OPT_BODY=$(echo "${OPTIMIZE_RESPONSE}" | sed '$d')

if [ "${OPT_CODE}" -eq 200 ] && echo "${OPT_BODY}" | grep -q '"scenario_id"[[:space:]]*:[[:space:]]*"CURL-VERIFY-01"'; then
    echo -e "${GREEN}✓ Optimization Endpoint Passed! HTTP 200 OK${NC}"
    
    # Check if jq is available to print formatted summary
    if command -v jq >/dev/null 2>&1; then
        echo "  Scenario ID:    $(echo "${OPT_BODY}" | jq -r '.scenario_id')"
        echo "  Total Cost:     $(echo "${OPT_BODY}" | jq -r '.total_cost_bdt') BDT"
        echo "  Total Grid:     $(echo "${OPT_BODY}" | jq -r '.total_grid_kwh') kWh"
        echo "  Peak Grid:      $(echo "${OPT_BODY}" | jq -r '.peak_grid_kwh') kWh"
        echo "  Plan Summary:   $(echo "${OPT_BODY}" | jq -r '.plan_summary')"
    else
        echo "  Response received successfully."
    fi
else
    echo -e "${RED}✗ Optimization Endpoint Failed! HTTP Status: ${OPT_CODE}${NC}"
    echo "  Response: ${OPT_BODY}"
    exit 1
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN} All API Endpoint Tests Passed Successfully!          ${NC}"
echo -e "${GREEN}======================================================${NC}"
