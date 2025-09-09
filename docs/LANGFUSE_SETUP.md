# Langfuse Setup Guide

Langfuse provides LLM observability, tracing, analytics, and cost monitoring for your AI Slack Bot.

## 🚀 Quick Setup

### 1. Get Langfuse Credentials

**Option A: Langfuse Cloud (Recommended)**
1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com)
2. Create a new project
3. Copy your API keys from the project settings

**Option B: Self-Hosted**
1. Deploy Langfuse using their [self-hosting guide](https://langfuse.com/docs/deployment/self-host)
2. Use your custom host URL

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Langfuse Configuration
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key-here
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key-here
LANGFUSE_HOST=https://cloud.langfuse.com  # or your self-hosted URL
LANGFUSE_DEBUG=false
```

### 3. Install Dependencies

Langfuse is already included in the project dependencies:

```bash
# Already in requirements
langfuse>=3.3.0
```

### 4. Verify Setup

1. **Restart your bot** to pick up the new configuration
2. **Check the health dashboard** at `http://localhost:8080/ui`
3. **Langfuse service** should show as "Healthy" with "Observability enabled"

## 🔧 Troubleshooting

### Common Issues

**❌ "Langfuse not available - tracing will be disabled"**
- **Cause**: Missing `langfuse` package
- **Fix**: Run `pip install langfuse>=3.3.0` or `make install`

**❌ "ImportError: No module named 'langfuse.decorators'"**
- **Cause**: Outdated Langfuse version (fixed in v3.3+)
- **Fix**: Update to `langfuse>=3.3.0` - the bot now imports from `langfuse` directly

**❌ "Enabled but client failed to initialize"**
- **Cause**: Invalid credentials or network issues
- **Fix**: Verify your `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST`

**❌ "Disabled in configuration"**
- **Cause**: `LANGFUSE_ENABLED=false` or missing credentials
- **Fix**: Set `LANGFUSE_ENABLED=true` and provide valid keys

### Health Dashboard Status Meanings

- **🟢 Healthy**: Langfuse is configured and working
  - Shows: "Observability enabled • [host URL]"

- **🔴 Unhealthy**: Configuration issues
  - Shows specific error message for troubleshooting

- **⚪ Disabled**: Not configured or intentionally disabled
  - Shows reason (missing keys, disabled setting, etc.)

## 📊 What Gets Tracked

### LLM Calls
- **Provider & Model**: OpenAI GPT-4, Anthropic Claude, etc.
- **Token Usage**: Input/output tokens and costs
- **Latency**: Response generation time
- **Status**: Success/failure with error details

### RAG Operations  
- **Retrieval**: Vector search queries and results
- **Context**: Which documents were retrieved
- **Quality**: Relevance scores and reranking

### Conversations
- **User Sessions**: Grouped by Slack thread
- **User Behavior**: Message patterns and popular features
- **Bot Performance**: Response quality and user satisfaction

### Costs & Analytics
- **Token Costs**: Per user, conversation, and model
- **Usage Patterns**: Peak times, heavy users
- **Model Performance**: Which models work best
- **Prompt Engineering**: Optimize prompts based on data

## 🔗 Integration Details

### Automatic Tracing
The bot automatically traces all LLM interactions with:
- **Conversation context**: Slack user and thread info
- **RAG context**: Retrieved documents and search queries  
- **Custom metadata**: Bot configuration and feature usage
- **Error tracking**: Failed requests and debugging info

### Dashboard Integration
- **Health monitoring**: Status visible in bot health dashboard
- **Real-time status**: Updates every 10 seconds
- **Configuration validation**: Checks credentials and connectivity

## 🎯 Best Practices

### Development
- Set `LANGFUSE_DEBUG=true` for detailed logging during development
- Use separate Langfuse projects for dev/staging/prod environments

### Production
- Monitor costs through Langfuse dashboard
- Set up alerts for high token usage
- Review conversation analytics monthly
- Use insights to optimize prompts and reduce costs

### Privacy
- Langfuse stores conversation data for analytics
- Review their [privacy policy](https://langfuse.com/privacy)
- Consider self-hosting for sensitive data

## 📈 Complementary Monitoring

Langfuse works alongside your existing monitoring stack:

### Your Current Stack (Keep!)
- **Prometheus/Grafana**: Infrastructure metrics
- **Loki**: Application logs  
- **Health dashboard**: Service status

### Langfuse Adds
- **LLM-specific insights**: Token costs, model performance
- **Conversation analytics**: User behavior, popular features
- **AI debugging**: Why responses succeed/fail
- **Cost optimization**: Identify expensive usage patterns

Together they provide complete observability for your AI Slack Bot! 🚀
