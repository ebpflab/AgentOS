#!/usr/bin/env bash
# CI/CD Status Monitor for AgentOS
# Usage: ./scripts/monitor-ci.sh [--webhook SLACK_WEBHOOK] [--interval 300]

REPO="ebpflab/AgentOS"
WORKFLOW="ci.yml"
INTERVAL=${2:-300}  # Default 5 minutes
SLACK_WEBHOOK=${SLACK_WEBHOOK:-""}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

check_gh_cli() {
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) not found. Install from: https://cli.github.com/"
        exit 1
    fi
}

get_latest_run() {
    gh run list -R "$REPO" -w "$WORKFLOW" --limit 1 --json databaseId,name,status,conclusion,url,createdAt
}

send_slack_notification() {
    local status=$1
    local conclusion=$2
    local run_url=$3
    local run_name=$4

    if [ -z "$SLACK_WEBHOOK" ]; then
        return
    fi

    local color="good"
    local emoji="✅"
    if [ "$conclusion" = "failure" ]; then
        color="danger"
        emoji="❌"
    elif [ "$status" = "in_progress" ]; then
        color="warning"
        emoji="⏳"
    fi

    local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$emoji AgentOS CI Pipeline",
            "text": "**Status:** $status\n**Conclusion:** $conclusion\n**Run:** $run_name",
            "actions": [
                {
                    "type": "button",
                    "text": "View Details",
                    "url": "$run_url"
                }
            ],
            "footer": "AgentOS CI Monitor",
            "ts": $(date +%s)
        }
    ]
}
EOF
)
    curl -X POST -H 'Content-type: application/json' \
        --data "$payload" \
        "$SLACK_WEBHOOK" 2>/dev/null
}

monitor_loop() {
    local last_conclusion=""

    while true; do
        log_info "Checking CI status for $REPO..."

        # Get latest run
        local run_data=$(get_latest_run)

        if [ -z "$run_data" ]; then
            log_error "Failed to fetch run data"
            sleep "$INTERVAL"
            continue
        fi

        # Parse JSON (requires jq)
        if ! command -v jq &> /dev/null; then
            log_error "jq not found. Install from: https://stedolan.github.io/jq/"
            exit 1
        fi

        local status=$(echo "$run_data" | jq -r '.[0].status // "unknown"')
        local conclusion=$(echo "$run_data" | jq -r '.[0].conclusion // "null"')
        local url=$(echo "$run_data" | jq -r '.[0].url // "unknown"')
        local name=$(echo "$run_data" | jq -r '.[0].name // "unknown"')

        # Display status
        case "$status" in
            "completed")
                if [ "$conclusion" = "success" ]; then
                    log_success "CI Pipeline PASSED"
                    echo "  Run: $name"
                    echo "  URL: $url"
                elif [ "$conclusion" = "failure" ]; then
                    log_error "CI Pipeline FAILED"
                    echo "  Run: $name"
                    echo "  URL: $url"

                    # Send Slack notification only on state change
                    if [ "$last_conclusion" != "failure" ]; then
                        send_slack_notification "completed" "failure" "$url" "$name"
                    fi
                fi
                ;;
            "in_progress")
                log_warning "CI Pipeline IN PROGRESS..."
                echo "  Run: $name"
                ;;
            *)
                log_warning "Unknown status: $status"
                ;;
        esac

        last_conclusion="$conclusion"

        echo "---"
        echo "Checking again in ${INTERVAL}s... (Press Ctrl+C to exit)"
        sleep "$INTERVAL"
    done
}

print_usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --webhook WEBHOOK_URL    Slack webhook URL for notifications
  --interval SECONDS       Check interval in seconds (default: 300)
  --help                   Show this help message

Example:
  $0 --webhook https://hooks.slack.com/... --interval 600
  $0 --interval 300
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --webhook)
            SLACK_WEBHOOK="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Main
check_gh_cli
log_info "Starting CI Monitor for $REPO"
log_info "Workflow: $WORKFLOW"
log_info "Check interval: ${INTERVAL}s"
if [ -n "$SLACK_WEBHOOK" ]; then
    log_info "Slack notifications: ENABLED"
else
    log_warning "Slack notifications: DISABLED"
fi
echo "---"

monitor_loop
