#!/usr/bin/env bash
# Quick reference for CI/CD operations
# Source this file or run individual functions

export REPO="ebpflab/AgentOS"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============ PR Operations ============

pr_list() {
    echo -e "${BLUE}📋 Open PRs:${NC}"
    gh pr list -R "$REPO" --state open --json number,title,author,createdAt
}

pr_view() {
    local pr_number=$1
    if [ -z "$pr_number" ]; then
        echo "Usage: pr_view <PR_NUMBER>"
        return 1
    fi
    gh pr view "$pr_number" -R "$REPO"
}

pr_comment() {
    local pr_number=$1
    local comment=$2
    if [ -z "$pr_number" ] || [ -z "$comment" ]; then
        echo "Usage: pr_comment <PR_NUMBER> '<COMMENT>'"
        return 1
    fi
    gh pr comment "$pr_number" -R "$REPO" -b "$comment"
    echo -e "${GREEN}✓ Comment added${NC}"
}

pr_merge() {
    local pr_number=$1
    if [ -z "$pr_number" ]; then
        echo "Usage: pr_merge <PR_NUMBER>"
        return 1
    fi
    gh pr merge "$pr_number" -R "$REPO" --squash
    echo -e "${GREEN}✓ PR merged${NC}"
}

# ============ Workflow Operations ============

ci_status() {
    echo -e "${BLUE}🔄 Latest CI Runs:${NC}"
    gh run list -R "$REPO" -w ci.yml --limit 5 --json status,conclusion,name,createdAt
}

ci_logs() {
    local run_id=$1
    if [ -z "$run_id" ]; then
        echo "Usage: ci_logs <RUN_ID>"
        echo "Get RUN_ID from: ci_status"
        return 1
    fi
    gh run view "$run_id" -R "$REPO" --log
}

ci_rerun() {
    local run_id=$1
    if [ -z "$run_id" ]; then
        echo "Usage: ci_rerun <RUN_ID>"
        return 1
    fi
    gh run rerun "$run_id" -R "$REPO"
    echo -e "${GREEN}✓ Workflow rerun triggered${NC}"
}

# ============ Issue Operations ============

issue_list() {
    echo -e "${BLUE}📌 Open Issues:${NC}"
    gh issue list -R "$REPO" --state open --json number,title,labels,createdAt
}

issue_create() {
    local title=$1
    local body=$2
    if [ -z "$title" ]; then
        echo "Usage: issue_create '<TITLE>' '<BODY>'"
        return 1
    fi
    gh issue create -R "$REPO" --title "$title" --body "${body:-}"
}

ci_failed_issues() {
    echo -e "${BLUE}🚨 CI Failure Issues:${NC}"
    gh issue list -R "$REPO" --state open --label ci-failure --json number,title,createdAt
}

# ============ Monitoring ============

monitor_ci() {
    local interval=${1:-300}
    echo -e "${BLUE}🏥 Starting CI Monitor (interval: ${interval}s)${NC}"
    bash "$(dirname "${BASH_SOURCE[0]}")/monitor-ci.sh" --interval "$interval"
}

# ============ Analytics ============

pr_stats() {
    echo -e "${BLUE}📊 PR Statistics:${NC}"
    echo -e "  ${YELLOW}Open PRs:${NC}"
    gh pr list -R "$REPO" --state open | wc -l
    echo -e "  ${YELLOW}Closed PRs (last 7 days):${NC}"
    gh pr list -R "$REPO" --state closed --search "closed:>$(date -u -d '-7 days' +%Y-%m-%d)" | wc -l
}

ci_success_rate() {
    echo -e "${BLUE}📈 CI Success Rate (last 10 runs):${NC}"
    local total=0
    local success=0
    gh run list -R "$REPO" -w ci.yml --limit 10 --json conclusion | \
    while read conclusion; do
        ((total++))
        if echo "$conclusion" | grep -q success; then
            ((success++))
        fi
    done
    echo "Success: $success / $total"
}

# ============ Setup ============

setup_github_mcp() {
    echo -e "${BLUE}📦 Installing GitHub MCP...${NC}"
    claude mcp add github npx @modelcontextprotocol/server-github
    echo -e "${GREEN}✓ GitHub MCP installed${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Get a GitHub token: https://github.com/settings/tokens"
    echo "2. Add to ~/.claude/settings.json:"
    cat <<'EOF'
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
EOF
}

# ============ Help ============

ci_help() {
    cat <<'EOF'
AgentOS CI/CD Quick Reference
==============================

📋 PR Operations:
  pr_list              — List all open PRs
  pr_view <NUMBER>     — View PR details
  pr_comment <N> "<MSG>" — Add comment to PR
  pr_merge <NUMBER>    — Merge PR

🔄 Workflow Operations:
  ci_status            — Show latest CI runs
  ci_logs <RUN_ID>     — View run logs
  ci_rerun <RUN_ID>    — Rerun failed workflow

📌 Issue Operations:
  issue_list           — List open issues
  issue_create "<TITLE>" — Create new issue
  ci_failed_issues     — Show CI failure issues

🏥 Monitoring:
  monitor_ci [INTERVAL] — Monitor CI status (default: 300s)

📊 Analytics:
  pr_stats             — PR statistics
  ci_success_rate      — CI success rate

📦 Setup:
  setup_github_mcp     — Install GitHub MCP

Examples:
  pr_list
  pr_view 42
  pr_comment 42 "Looks good! 👍"
  ci_status
  ci_rerun <RUN_ID>
  monitor_ci 600
  setup_github_mcp

Set REPO environment variable to use different repo:
  export REPO="your-org/your-repo"
EOF
}

# If sourced, export functions; if run directly, show help
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    ci_help
else
    export -f pr_list pr_view pr_comment pr_merge
    export -f ci_status ci_logs ci_rerun
    export -f issue_list issue_create ci_failed_issues
    export -f monitor_ci pr_stats ci_success_rate
    export -f setup_github_mcp ci_help
fi
