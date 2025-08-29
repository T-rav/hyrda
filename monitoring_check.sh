#!/bin/bash

# Simple monitoring script for Slack bot
# Run this via cron every 5 minutes: */5 * * * * /path/to/monitoring_check.sh

LOG_FILE="/var/log/slack-bot-monitor.log"
CONTAINER_NAME="insight-mesh-slack-bot"
HEALTH_URL="http://localhost:8080/health"
ALERT_EMAIL="admin@yourcompany.com"  # Change this
ALERT_WEBHOOK=""  # Optional: Slack webhook for alerts

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Send alert function
send_alert() {
    local message="$1"
    local subject="Slack Bot Alert - $(hostname)"

    log "ALERT: $message"

    # Email alert (requires mailutils or similar)
    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    fi

    # Slack webhook alert (optional)
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$subject: $message\"}" \
            "$ALERT_WEBHOOK" &> /dev/null
    fi
}

# Check if running in Docker
if command -v docker &> /dev/null; then
    # Docker health check
    if docker ps --format "table {{.Names}}" | grep -q "$CONTAINER_NAME"; then
        log "Container $CONTAINER_NAME is running"

        # Check container health status
        HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null)
        if [ "$HEALTH_STATUS" = "unhealthy" ]; then
            send_alert "Container $CONTAINER_NAME is unhealthy. Restarting..."
            docker restart "$CONTAINER_NAME"
        elif [ "$HEALTH_STATUS" = "healthy" ]; then
            log "Container health check passed"
        else
            log "Health status: $HEALTH_STATUS"
        fi
    else
        send_alert "Container $CONTAINER_NAME is not running. Starting..."
        docker-compose -f docker-compose.prod.yml up -d
    fi
else
    # Process-based health check
    if pgrep -f "python.*app.py" > /dev/null; then
        log "Slack bot process is running"
    else
        send_alert "Slack bot process is not running"
    fi
fi

# HTTP health check
if curl -f -s "$HEALTH_URL" > /dev/null; then
    log "Health endpoint responding"
else
    send_alert "Health endpoint $HEALTH_URL is not responding"
fi

# Check disk space
DISK_USAGE=$(df /var/log | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    send_alert "Disk usage is high: ${DISK_USAGE}%"
fi

# Check memory usage (if running in Docker)
if command -v docker &> /dev/null && docker ps --format "table {{.Names}}" | grep -q "$CONTAINER_NAME"; then
    MEMORY_USAGE=$(docker stats --no-stream --format "table {{.MemPerc}}" "$CONTAINER_NAME" | tail -n 1 | sed 's/%//')
    if [ $(echo "$MEMORY_USAGE > 80" | bc -l 2>/dev/null || echo "0") -eq 1 ]; then
        send_alert "Memory usage is high: ${MEMORY_USAGE}%"
    fi
fi

log "Health check completed"
