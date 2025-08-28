#!/bin/bash

# Production deployment script for Insight Mesh Slack Bot
# Usage: ./deploy.sh [docker|systemd|monitoring]

set -e

DEPLOYMENT_TYPE=${1:-docker}
APP_DIR="/opt/slack-bot"
SERVICE_NAME="slack-bot"

echo "Starting deployment of Insight Mesh Slack Bot..."
echo "Deployment type: $DEPLOYMENT_TYPE"

# Check if running as root for system deployment
if [ "$DEPLOYMENT_TYPE" = "systemd" ] && [ "$EUID" -ne 0 ]; then
    echo "Please run systemd deployment as root"
    exit 1
fi

case $DEPLOYMENT_TYPE in
    "docker")
        echo "Deploying with Docker..."
        
        # Check if .env exists
        if [ ! -f .env ]; then
            echo "Error: .env file not found. Please create one with required variables:"
            echo "  SLACK_BOT_TOKEN=xoxb-..."
            echo "  SLACK_APP_TOKEN=xapp-..."
            echo "  LLM_API_URL=..."
            echo "  LLM_API_KEY=..."
            exit 1
        fi
        
        # Create logs directory
        mkdir -p logs
        
        # Build and start with Docker Compose
        docker-compose -f docker-compose.prod.yml down
        docker-compose -f docker-compose.prod.yml build
        docker-compose -f docker-compose.prod.yml up -d
        
        echo "Waiting for health check..."
        sleep 30
        
        # Verify deployment
        if curl -f http://localhost:8080/health > /dev/null 2>&1; then
            echo "✅ Deployment successful! Bot is healthy."
            echo "Health check: http://localhost:8080/health"
            echo "Logs: docker logs insight-mesh-slack-bot -f"
        else
            echo "❌ Deployment failed. Health check failed."
            docker-compose -f docker-compose.prod.yml logs
            exit 1
        fi
        ;;
        
    "systemd")
        echo "Deploying with systemd..."
        
        # Create user and directories
        if ! id "slack-bot" &>/dev/null; then
            useradd -r -m -d "$APP_DIR" -s /bin/bash slack-bot
        fi
        
        # Create application directory
        mkdir -p "$APP_DIR"/{logs,src}
        
        # Copy application files
        cp -r src/* "$APP_DIR/"
        cp .env "$APP_DIR/" 2>/dev/null || echo "Warning: .env file not found"
        
        # Set permissions
        chown -R slack-bot:slack-bot "$APP_DIR"
        
        # Create virtual environment
        sudo -u slack-bot python3 -m venv "$APP_DIR/venv"
        sudo -u slack-bot "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
        
        # Install systemd service
        cp systemd/slack-bot.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        systemctl restart "$SERVICE_NAME"
        
        echo "Waiting for service to start..."
        sleep 10
        
        # Verify deployment
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "✅ Deployment successful! Service is running."
            echo "Status: systemctl status $SERVICE_NAME"
            echo "Logs: journalctl -u $SERVICE_NAME -f"
            
            # Test health endpoint
            sleep 20
            if curl -f http://localhost:8080/health > /dev/null 2>&1; then
                echo "✅ Health check passed."
            else
                echo "⚠️ Service running but health check failed."
            fi
        else
            echo "❌ Deployment failed. Service not running."
            systemctl status "$SERVICE_NAME"
            exit 1
        fi
        ;;

    "monitoring")
        echo "Deploying with full monitoring stack..."
        
        # Check if .env exists
        if [ ! -f .env ]; then
            echo "Error: .env file not found. Please create one with required variables."
            exit 1
        fi
        
        # Create directories
        mkdir -p logs monitoring/grafana/{dashboards,datasources}
        
        # Deploy with monitoring stack
        docker-compose -f docker-compose.monitoring.yml down
        docker-compose -f docker-compose.monitoring.yml build
        docker-compose -f docker-compose.monitoring.yml up -d
        
        echo "Waiting for services to start..."
        sleep 60
        
        # Verify deployment
        if curl -f http://localhost:8080/health > /dev/null 2>&1; then
            echo "✅ Slack bot is healthy"
        else
            echo "❌ Slack bot health check failed"
        fi
        
        if curl -f http://localhost:9090 > /dev/null 2>&1; then
            echo "✅ Prometheus is running"
        else
            echo "⚠️ Prometheus not accessible"
        fi
        
        if curl -f http://localhost:3000 > /dev/null 2>&1; then
            echo "✅ Grafana is running"
        else
            echo "⚠️ Grafana not accessible"
        fi
        
        echo ""
        echo "🎉 Monitoring stack deployed!"
        echo ""
        echo "Access points:"
        echo "  Bot health: http://localhost:8080/health"
        echo "  Prometheus: http://localhost:9090"
        echo "  Grafana: http://localhost:3000 (admin/admin123)"
        echo "  AlertManager: http://localhost:9093"
        echo "  Container metrics: http://localhost:8081"
        ;;
        
    *)
        echo "Usage: $0 [docker|systemd|monitoring]"
        echo "  docker     - Deploy bot only with Docker Compose"
        echo "  systemd    - Deploy as systemd service"
        echo "  monitoring - Deploy with full monitoring stack (Prometheus, Grafana, etc.)"
        exit 1
        ;;
esac

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Verify the bot is responding in Slack"
echo "2. Set up monitoring cron job:"
echo "   */5 * * * * $(pwd)/monitoring_check.sh"
echo "3. Configure log rotation if needed"
echo "4. Set up external monitoring/alerting"