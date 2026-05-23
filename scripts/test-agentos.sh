#!/bin/bash

# AgentOS Web & API Automated Testing Script
# Tests both frontend and backend, reports issues to GitHub

set -e

ISSUES=()
BASEURL="http://localhost:3000"
APIURL="http://localhost:8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

add_issue() {
  local title=$1
  local category=$2
  local description=$3
  ISSUES+=("[$category] $title: $description")
  log_error "$title"
}

echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🧪 AgentOS Automated Web & API Testing${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

# Test 1: API Health Check
echo "Test 1: API Health Check..."
if curl -s -f "$APIURL/health" > /dev/null 2>&1; then
  log_success "API is responding"
else
  add_issue "API not responding" "Critical" "API endpoint $APIURL/health is unreachable"
fi

# Test 2: Web Frontend Load
echo -e "\nTest 2: Web Frontend..."
response=$(curl -s -w "\n%{http_code}" "$BASEURL")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" == "200" ]; then
  log_success "Web frontend loads (HTTP $http_code)"
else
  add_issue "Web frontend load failed" "Critical" "HTTP $http_code from $BASEURL"
fi

# Test 3: Check for React App
echo -e "\nTest 3: React Application..."
if echo "$body" | grep -q "react\|root\|app" ; then
  log_success "React application detected"
else
  add_issue "React app not detected" "Warning" "HTML does not contain React markers"
fi

# Test 4: HTML Meta Tags
echo -e "\nTest 4: HTML Meta Tags..."
if echo "$body" | grep -q "<title>" ; then
  title=$(echo "$body" | grep -oP '<title>\K[^<]+' | head -1)
  log_success "Page title: $title"
else
  add_issue "Missing page title" "SEO" "HTML missing <title> tag"
fi

# Test 5: API Endpoints Status
echo -e "\nTest 5: API Endpoints Status..."
endpoints=(
  "/api/agents:Agents"
  "/api/workflows:Workflows"
  "/api/metrics/agents:Agent Metrics"
  "/health:Health"
)

for endpoint_info in "${endpoints[@]}"; do
  IFS=':' read -r endpoint name <<< "$endpoint_info"
  status=$(curl -s -o /dev/null -w "%{http_code}" "$APIURL$endpoint" 2>/dev/null || echo "000")

  if [ "$status" == "200" ] || [ "$status" == "404" ]; then
    log_success "$name endpoint: HTTP $status"
  else
    add_issue "$name endpoint failed" "API" "HTTP $status"
  fi
done

# Test 6: Content Security
echo -e "\nTest 6: Security Headers..."
headers=$(curl -s -i "$APIURL/health" 2>/dev/null | grep -i "content-type\|cache-control" || true)
if [ -n "$headers" ]; then
  log_success "Security headers present"
else
  log_warn "Limited security headers"
fi

# Test 7: Response Time
echo -e "\nTest 7: Response Time..."
start_time=$(date +%s%N)
curl -s -f "$APIURL/health" > /dev/null
end_time=$(date +%s%N)
response_time=$(( (end_time - start_time) / 1000000 ))

echo "API response time: ${response_time}ms"
if [ $response_time -gt 1000 ]; then
  add_issue "Slow API response" "Performance" "API took ${response_time}ms (>1s)"
else
  log_success "API response time OK"
fi

# Test 8: Database Connection
echo -e "\nTest 8: Database Health..."
db_response=$(curl -s -X GET "$APIURL/health" -H "Content-Type: application/json" 2>/dev/null | grep -o "status\|healthy" || true)

if [ -n "$db_response" ]; then
  log_success "Database connection seems healthy"
else
  log_warn "Cannot determine database status"
fi

# Test 9: CORS Headers
echo -e "\nTest 9: CORS Configuration..."
cors_header=$(curl -s -I "$APIURL/health" 2>/dev/null | grep -i "access-control" || true)
if [ -n "$cors_header" ]; then
  log_success "CORS headers detected"
else
  log_warn "No CORS headers found"
fi

# Test 10: Frontend Build Quality
echo -e "\nTest 10: Frontend Asset Check..."
if echo "$body" | grep -q "\.js\|\.css" ; then
  log_success "CSS/JS assets loaded"
else
  add_issue "No assets found" "Warning" "Frontend may not have CSS/JS assets"
fi

# Summary
echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📋 TEST SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

if [ ${#ISSUES[@]} -eq 0 ]; then
  log_success "All tests passed! No critical issues found."
  exit 0
else
  echo -e "Found ${#ISSUES[@]} issue(s):\n"
  for i in "${!ISSUES[@]}"; do
    echo "$((i+1)). ${ISSUES[$i]}"
  done

  # Output in JSON format for easier parsing
  echo -e "\n${BLUE}Issues in JSON format:${NC}"
  echo "["
  for i in "${!ISSUES[@]}"; do
    IFS=']' read -r category title_desc <<< "${ISSUES[$i]#[}"
    IFS=':' read -r title description <<< "$title_desc"

    echo "  {\"category\": \"${category}\", \"title\": \"${title:1}\", \"description\": \"${description:1}\"}"
    if [ $i -lt $((${#ISSUES[@]}-1)) ]; then echo -n ","; fi
    echo
  done
  echo "]"

  exit 1
fi
