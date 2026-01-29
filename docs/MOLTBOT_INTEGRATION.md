# InsightMesh ↔ Moltbot Integration Architecture

## Vision

Combine the best of both platforms:
- **Moltbot**: Multi-channel message routing (12+ platforms)
- **InsightMesh**: Enterprise RAG, deep research agents, LangGraph capabilities

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                        Moltbot Gateway                          │
│  (Node.js/TypeScript - Multi-Channel Message Router)           │
│                                                                  │
│  WhatsApp │ Telegram │ Discord │ Signal │ Teams │ Matrix       │
│  iMessage │ Slack    │ BlueBubbles │ Google Chat │ Zalo        │
└────────────────┬───────────────────────────────────────────────┘
                 │
                 │ HTTP/REST API
                 ▼
┌────────────────────────────────────────────────────────────────┐
│               InsightMesh Agent Service Layer                   │
│                    (Python - FastAPI)                           │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐           │
│  │   RAG API   │  │ Agent API   │  │  Search API  │           │
│  │ Vector      │  │ Deep        │  │  Tavily/     │           │
│  │ Search      │  │ Research    │  │  Perplexity  │           │
│  └─────────────┘  └─────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │         InsightMesh Core Services                 │          │
│  │  • Qdrant Vector DB                               │          │
│  │  • LangGraph Agents                               │          │
│  │  • MySQL/Redis                                    │          │
│  │  • Langfuse Observability                         │          │
│  └──────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
```

## Two-Way Integration

### Phase 1: InsightMesh → Multi-Channel (Expand Connectors)
Add moltbot's channel support directly to InsightMesh

### Phase 2: Moltbot → InsightMesh Agents (API Integration)
Let moltbot call InsightMesh's advanced agent capabilities

---

# Phase 1: Multi-Channel Connectors for InsightMesh

## Architecture: Channel Adapter Pattern

### 1.1 Base Channel Interface

```python
# bot/channels/base.py
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass

@dataclass
class UnifiedMessage:
    """Platform-agnostic message representation"""
    text: str
    user_id: str
    channel_id: str
    platform: str  # slack, discord, telegram, etc.
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    attachments: list[dict] = None
    metadata: dict[str, Any] = None

@dataclass
class UnifiedResponse:
    """Platform-agnostic response"""
    text: str
    channel_id: str
    thread_id: Optional[str] = None
    attachments: list[dict] = None
    blocks: Optional[list] = None  # For rich formatting

class BaseChannelAdapter(ABC):
    """Base class for all channel adapters"""

    @abstractmethod
    async def send_message(
        self,
        response: UnifiedResponse
    ) -> tuple[bool, Optional[str]]:
        """Send message to channel. Returns (success, message_id)"""
        pass

    @abstractmethod
    async def process_event(self, event: dict) -> Optional[UnifiedMessage]:
        """Convert platform event to UnifiedMessage"""
        pass

    @abstractmethod
    async def get_thread_history(
        self,
        channel_id: str,
        thread_id: str
    ) -> list[UnifiedMessage]:
        """Retrieve thread/conversation history"""
        pass

    @abstractmethod
    async def authenticate(self) -> bool:
        """Verify credentials and connection"""
        pass

    @abstractmethod
    def supports_threads(self) -> bool:
        """Does this platform support threaded conversations?"""
        pass

    @abstractmethod
    def supports_attachments(self) -> bool:
        """Does this platform support file attachments?"""
        pass
```

### 1.2 Channel Adapter Implementations

#### Discord Adapter

```python
# bot/channels/discord_adapter.py
import discord
from discord.ext import commands
from bot.channels.base import BaseChannelAdapter, UnifiedMessage, UnifiedResponse

class DiscordAdapter(BaseChannelAdapter):
    """Discord channel adapter"""

    def __init__(self, token: str, bot_user_id: str):
        self.token = token
        self.bot_user_id = bot_user_id
        self.client: Optional[discord.Client] = None
        self.intents = discord.Intents.default()
        self.intents.message_content = True

    async def authenticate(self) -> bool:
        """Initialize Discord client"""
        try:
            self.client = discord.Client(intents=self.intents)

            @self.client.event
            async def on_ready():
                logger.info(f"Discord bot ready: {self.client.user}")

            @self.client.event
            async def on_message(message):
                if message.author.bot:
                    return
                await self.handle_discord_message(message)

            # Start in background task
            asyncio.create_task(self.client.start(self.token))
            return True
        except Exception as e:
            logger.error(f"Discord auth failed: {e}")
            return False

    async def process_event(self, message: discord.Message) -> Optional[UnifiedMessage]:
        """Convert Discord message to UnifiedMessage"""
        # Skip bot messages
        if message.author.bot:
            return None

        # Check if bot is mentioned
        bot_mentioned = any(
            mention.id == int(self.bot_user_id)
            for mention in message.mentions
        )

        # In DMs or if mentioned
        if isinstance(message.channel, discord.DMChannel) or bot_mentioned:
            # Clean mentions from text
            text = message.content
            for mention in message.mentions:
                text = text.replace(f'<@{mention.id}>', '').strip()

            return UnifiedMessage(
                text=text,
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
                platform="discord",
                thread_id=str(message.channel.id) if message.reference else None,
                message_id=str(message.id),
                attachments=[
                    {"url": att.url, "filename": att.filename}
                    for att in message.attachments
                ],
                metadata={
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "author_name": str(message.author),
                }
            )
        return None

    async def send_message(
        self,
        response: UnifiedResponse
    ) -> tuple[bool, Optional[str]]:
        """Send message to Discord channel"""
        try:
            channel = await self.client.fetch_channel(int(response.channel_id))

            # Handle threading (Discord uses replies)
            reference = None
            if response.thread_id:
                try:
                    ref_message = await channel.fetch_message(int(response.thread_id))
                    reference = ref_message.to_reference()
                except:
                    pass

            sent_message = await channel.send(
                content=response.text,
                reference=reference
            )
            return True, str(sent_message.id)
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return False, None

    async def get_thread_history(
        self,
        channel_id: str,
        thread_id: str
    ) -> list[UnifiedMessage]:
        """Get Discord thread history"""
        try:
            channel = await self.client.fetch_channel(int(channel_id))
            messages = []

            async for msg in channel.history(limit=50):
                if msg.reference and str(msg.reference.message_id) == thread_id:
                    unified = await self.process_event(msg)
                    if unified:
                        messages.append(unified)

            return messages[::-1]  # Chronological order
        except Exception as e:
            logger.error(f"Discord history fetch failed: {e}")
            return []

    def supports_threads(self) -> bool:
        return True  # Via message references

    def supports_attachments(self) -> bool:
        return True
```

#### Telegram Adapter

```python
# bot/channels/telegram_adapter.py
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters
from bot.channels.base import BaseChannelAdapter, UnifiedMessage, UnifiedResponse

class TelegramAdapter(BaseChannelAdapter):
    """Telegram channel adapter"""

    def __init__(self, token: str, bot_username: str):
        self.token = token
        self.bot_username = bot_username
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None

    async def authenticate(self) -> bool:
        """Initialize Telegram bot"""
        try:
            self.application = Application.builder().token(self.token).build()
            self.bot = self.application.bot

            # Register message handler
            self.application.add_handler(
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.handle_telegram_message
                )
            )

            # Start polling in background
            asyncio.create_task(self.application.run_polling())
            return True
        except Exception as e:
            logger.error(f"Telegram auth failed: {e}")
            return False

    async def process_event(self, update: Update) -> Optional[UnifiedMessage]:
        """Convert Telegram update to UnifiedMessage"""
        message = update.message
        if not message or not message.text:
            return None

        # Check if in private chat or bot mentioned
        is_private = message.chat.type == "private"
        bot_mentioned = f"@{self.bot_username}" in message.text

        if is_private or bot_mentioned:
            # Clean bot mention
            text = message.text.replace(f"@{self.bot_username}", "").strip()

            return UnifiedMessage(
                text=text,
                user_id=str(message.from_user.id),
                channel_id=str(message.chat.id),
                platform="telegram",
                thread_id=str(message.message_thread_id) if message.message_thread_id else None,
                message_id=str(message.message_id),
                attachments=[],
                metadata={
                    "chat_type": message.chat.type,
                    "username": message.from_user.username,
                }
            )
        return None

    async def send_message(
        self,
        response: UnifiedResponse
    ) -> tuple[bool, Optional[str]]:
        """Send message to Telegram chat"""
        try:
            sent_message = await self.bot.send_message(
                chat_id=int(response.channel_id),
                text=response.text,
                reply_to_message_id=int(response.thread_id) if response.thread_id else None,
                parse_mode="Markdown"
            )
            return True, str(sent_message.message_id)
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False, None

    async def get_thread_history(
        self,
        channel_id: str,
        thread_id: str
    ) -> list[UnifiedMessage]:
        """Telegram doesn't provide easy thread history access"""
        # Would need to maintain local cache
        return []

    def supports_threads(self) -> bool:
        return True  # Via reply_to_message

    def supports_attachments(self) -> bool:
        return True
```

#### WhatsApp Adapter (via Twilio)

```python
# bot/channels/whatsapp_adapter.py
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from bot.channels.base import BaseChannelAdapter, UnifiedMessage, UnifiedResponse

class WhatsAppAdapter(BaseChannelAdapter):
    """WhatsApp channel adapter via Twilio"""

    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number  # whatsapp:+14155238886
        self.client: Optional[Client] = None

    async def authenticate(self) -> bool:
        """Initialize Twilio client"""
        try:
            self.client = Client(self.account_sid, self.auth_token)
            return True
        except Exception as e:
            logger.error(f"WhatsApp auth failed: {e}")
            return False

    async def process_event(self, webhook_data: dict) -> Optional[UnifiedMessage]:
        """Convert Twilio webhook to UnifiedMessage"""
        # Twilio webhook provides: From, Body, MediaUrl, etc.
        from_number = webhook_data.get("From", "")
        body = webhook_data.get("Body", "")

        if not from_number.startswith("whatsapp:"):
            return None

        return UnifiedMessage(
            text=body,
            user_id=from_number.replace("whatsapp:", ""),
            channel_id=from_number,  # Each user is their own channel
            platform="whatsapp",
            thread_id=None,  # WhatsApp doesn't have threads
            message_id=webhook_data.get("MessageSid"),
            attachments=[
                {"url": webhook_data.get(f"MediaUrl{i}")}
                for i in range(int(webhook_data.get("NumMedia", 0)))
            ],
            metadata={
                "profile_name": webhook_data.get("ProfileName"),
            }
        )

    async def send_message(
        self,
        response: UnifiedResponse
    ) -> tuple[bool, Optional[str]]:
        """Send WhatsApp message via Twilio"""
        try:
            message = self.client.messages.create(
                from_=self.phone_number,
                body=response.text,
                to=f"whatsapp:{response.channel_id}"
            )
            return True, message.sid
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False, None

    async def get_thread_history(
        self,
        channel_id: str,
        thread_id: str
    ) -> list[UnifiedMessage]:
        """WhatsApp doesn't have threads"""
        return []

    def supports_threads(self) -> bool:
        return False

    def supports_attachments(self) -> bool:
        return True
```

### 1.3 Channel Router

```python
# bot/gateway/channel_router.py
from typing import Optional
from bot.channels.base import BaseChannelAdapter, UnifiedMessage, UnifiedResponse
from bot.channels.slack_adapter import SlackAdapter
from bot.channels.discord_adapter import DiscordAdapter
from bot.channels.telegram_adapter import TelegramAdapter
from bot.channels.whatsapp_adapter import WhatsAppAdapter

class ChannelRouter:
    """Routes messages across all connected channels"""

    def __init__(self):
        self.adapters: dict[str, BaseChannelAdapter] = {}
        self._initialized = False

    async def register_adapter(
        self,
        platform: str,
        adapter: BaseChannelAdapter
    ) -> bool:
        """Register a channel adapter"""
        if await adapter.authenticate():
            self.adapters[platform] = adapter
            logger.info(f"Registered {platform} adapter")
            return True
        else:
            logger.error(f"Failed to register {platform} adapter")
            return False

    async def initialize_from_config(self, config: dict):
        """Initialize all adapters from configuration"""
        # Slack
        if config.get("slack"):
            slack = SlackAdapter(
                token=config["slack"]["bot_token"],
                app_token=config["slack"]["app_token"]
            )
            await self.register_adapter("slack", slack)

        # Discord
        if config.get("discord"):
            discord = DiscordAdapter(
                token=config["discord"]["token"],
                bot_user_id=config["discord"]["bot_user_id"]
            )
            await self.register_adapter("discord", discord)

        # Telegram
        if config.get("telegram"):
            telegram = TelegramAdapter(
                token=config["telegram"]["token"],
                bot_username=config["telegram"]["username"]
            )
            await self.register_adapter("telegram", telegram)

        # WhatsApp
        if config.get("whatsapp"):
            whatsapp = WhatsAppAdapter(
                account_sid=config["whatsapp"]["account_sid"],
                auth_token=config["whatsapp"]["auth_token"],
                phone_number=config["whatsapp"]["phone_number"]
            )
            await self.register_adapter("whatsapp", whatsapp)

        self._initialized = True

    async def route_message(
        self,
        platform: str,
        event: dict
    ) -> Optional[UnifiedMessage]:
        """Route incoming message from any platform"""
        adapter = self.adapters.get(platform)
        if not adapter:
            logger.warning(f"No adapter for platform: {platform}")
            return None

        return await adapter.process_event(event)

    async def send_response(
        self,
        platform: str,
        response: UnifiedResponse
    ) -> tuple[bool, Optional[str]]:
        """Send response to specific platform"""
        adapter = self.adapters.get(platform)
        if not adapter:
            logger.error(f"No adapter for platform: {platform}")
            return False, None

        return await adapter.send_message(response)

    def get_supported_platforms(self) -> list[str]:
        """List all registered platforms"""
        return list(self.adapters.keys())
```

### 1.4 Unified Message Handler

```python
# bot/handlers/unified_message_handler.py
from bot.gateway.channel_router import ChannelRouter
from bot.channels.base import UnifiedMessage, UnifiedResponse
from bot.services.llm_service import LLMService
from bot.services.rag_client import RAGClient

class UnifiedMessageHandler:
    """Platform-agnostic message processing"""

    def __init__(
        self,
        router: ChannelRouter,
        llm_service: LLMService,
        rag_client: RAGClient
    ):
        self.router = router
        self.llm_service = llm_service
        self.rag_client = rag_client

    async def handle_message(self, message: UnifiedMessage) -> UnifiedResponse:
        """Process message from any platform"""

        # 1. Get conversation history (platform-specific)
        adapter = self.router.adapters[message.platform]
        history = []
        if message.thread_id and adapter.supports_threads():
            history = await adapter.get_thread_history(
                message.channel_id,
                message.thread_id
            )

        # 2. RAG retrieval (if enabled)
        context = ""
        if self.rag_client:
            rag_results = await self.rag_client.retrieve(
                query=message.text,
                user_id=message.user_id
            )
            context = rag_results.get("context", "")

        # 3. LLM generation
        llm_response = await self.llm_service.generate(
            prompt=message.text,
            context=context,
            history=[{"role": "user", "content": m.text} for m in history]
        )

        # 4. Create platform-agnostic response
        return UnifiedResponse(
            text=llm_response,
            channel_id=message.channel_id,
            thread_id=message.thread_id
        )

    async def process_and_respond(self, message: UnifiedMessage):
        """Complete flow: process message and send response"""
        try:
            response = await self.handle_message(message)
            success, msg_id = await self.router.send_response(
                message.platform,
                response
            )

            if success:
                logger.info(
                    f"Responded on {message.platform}: {msg_id}"
                )
            else:
                logger.error(
                    f"Failed to respond on {message.platform}"
                )
        except Exception as e:
            logger.error(f"Message processing failed: {e}")
```

### 1.5 Configuration

```yaml
# config/channels.yaml
channels:
  slack:
    enabled: true
    bot_token: ${SLACK_BOT_TOKEN}
    app_token: ${SLACK_APP_TOKEN}

  discord:
    enabled: true
    token: ${DISCORD_BOT_TOKEN}
    bot_user_id: ${DISCORD_BOT_USER_ID}

  telegram:
    enabled: true
    token: ${TELEGRAM_BOT_TOKEN}
    username: ${TELEGRAM_BOT_USERNAME}

  whatsapp:
    enabled: false  # Requires Twilio setup
    account_sid: ${TWILIO_ACCOUNT_SID}
    auth_token: ${TWILIO_AUTH_TOKEN}
    phone_number: ${TWILIO_WHATSAPP_NUMBER}

  signal:
    enabled: false  # Requires signal-cli setup
    phone_number: ${SIGNAL_PHONE_NUMBER}

  matrix:
    enabled: false
    homeserver: ${MATRIX_HOMESERVER}
    access_token: ${MATRIX_ACCESS_TOKEN}

  teams:
    enabled: false
    app_id: ${TEAMS_APP_ID}
    app_password: ${TEAMS_APP_PASSWORD}
```

---

# Phase 2: InsightMesh Agent API for Moltbot

## 2.1 Agent Service API

```python
# agent-service/api/external.py
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, AsyncIterator
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/external", tags=["External API"])

class AgentRequest(BaseModel):
    """Request to invoke InsightMesh agent"""
    query: str
    user_id: str
    platform: str  # moltbot, slack, discord, etc.
    context: Optional[dict] = None
    stream: bool = False

class AgentResponse(BaseModel):
    """Response from InsightMesh agent"""
    response: str
    sources: list[dict] = []
    trace_id: Optional[str] = None
    metadata: dict = {}

@router.post("/agent/invoke")
async def invoke_agent(
    request: AgentRequest,
    x_api_key: str = Header(...),
) -> AgentResponse:
    """
    Invoke InsightMesh deep research agent

    This endpoint allows external systems (like moltbot) to trigger
    InsightMesh's advanced RAG + research capabilities.
    """
    # Validate API key
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Rate limiting
    if not check_rate_limit(request.user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Invoke agent
    result = await agent_service.invoke_deep_research(
        query=request.query,
        user_id=request.user_id,
        context=request.context
    )

    return AgentResponse(
        response=result.answer,
        sources=result.sources,
        trace_id=result.trace_id,
        metadata={
            "platform": request.platform,
            "processing_time": result.duration,
            "tokens_used": result.tokens
        }
    )

@router.post("/agent/invoke-stream")
async def invoke_agent_stream(
    request: AgentRequest,
    x_api_key: str = Header(...),
):
    """
    Invoke InsightMesh agent with streaming response

    Returns Server-Sent Events (SSE) for real-time streaming.
    """
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    async def generate():
        async for chunk in agent_service.invoke_deep_research_stream(
            query=request.query,
            user_id=request.user_id,
            context=request.context
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )

@router.post("/rag/query")
async def rag_query(
    query: str,
    user_id: str,
    limit: int = 10,
    x_api_key: str = Header(...),
):
    """
    Direct RAG query without agent orchestration

    Returns relevant documents from vector store.
    """
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    results = await rag_service.retrieve(
        query=query,
        user_id=user_id,
        limit=limit
    )

    return {
        "documents": results.documents,
        "scores": results.scores,
        "metadata": results.metadata
    }

@router.post("/search/web")
async def web_search(
    query: str,
    search_type: str = "quick",  # quick, deep
    x_api_key: str = Header(...),
):
    """
    Web search via Tavily/Perplexity

    search_type:
    - quick: Tavily fast search
    - deep: Perplexity deep research with citations
    """
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    if search_type == "quick":
        results = await tavily_client.search(query)
    else:
        results = await perplexity_client.search(query)

    return results
```

## 2.2 Moltbot Skill/Plugin

```typescript
// moltbot-skills/insightmesh-agent.ts
import axios from 'axios';
import { EventEmitter } from 'events';

export interface InsightMeshConfig {
  apiUrl: string;
  apiKey: string;
  timeout?: number;
}

export interface AgentRequest {
  query: string;
  userId: string;
  platform: string;
  context?: Record<string, any>;
  stream?: boolean;
}

export interface AgentResponse {
  response: string;
  sources: Array<{
    title: string;
    url: string;
    snippet: string;
  }>;
  traceId?: string;
  metadata: Record<string, any>;
}

export class InsightMeshAgent extends EventEmitter {
  private config: InsightMeshConfig;

  constructor(config: InsightMeshConfig) {
    super();
    this.config = {
      timeout: 60000,
      ...config
    };
  }

  /**
   * Invoke InsightMesh deep research agent
   */
  async invoke(request: AgentRequest): Promise<AgentResponse> {
    try {
      const response = await axios.post(
        `${this.config.apiUrl}/external/agent/invoke`,
        request,
        {
          headers: {
            'X-API-Key': this.config.apiKey,
            'Content-Type': 'application/json'
          },
          timeout: this.config.timeout
        }
      );

      return response.data;
    } catch (error) {
      console.error('InsightMesh agent invocation failed:', error);
      throw error;
    }
  }

  /**
   * Invoke agent with streaming response
   */
  async invokeStream(
    request: AgentRequest,
    onChunk: (chunk: string) => void
  ): Promise<void> {
    const response = await axios.post(
      `${this.config.apiUrl}/external/agent/invoke-stream`,
      { ...request, stream: true },
      {
        headers: {
          'X-API-Key': this.config.apiKey,
          'Content-Type': 'application/json'
        },
        responseType: 'stream'
      }
    );

    return new Promise((resolve, reject) => {
      response.data.on('data', (chunk: Buffer) => {
        const text = chunk.toString();
        const lines = text.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            onChunk(data);
            this.emit('chunk', data);
          }
        }
      });

      response.data.on('end', () => {
        this.emit('complete');
        resolve();
      });

      response.data.on('error', (error: Error) => {
        this.emit('error', error);
        reject(error);
      });
    });
  }

  /**
   * Direct RAG query
   */
  async ragQuery(
    query: string,
    userId: string,
    limit: number = 10
  ): Promise<any> {
    const response = await axios.post(
      `${this.config.apiUrl}/external/rag/query`,
      { query, user_id: userId, limit },
      {
        headers: {
          'X-API-Key': this.config.apiKey
        }
      }
    );

    return response.data;
  }

  /**
   * Web search
   */
  async webSearch(
    query: string,
    searchType: 'quick' | 'deep' = 'quick'
  ): Promise<any> {
    const response = await axios.post(
      `${this.config.apiUrl}/external/search/web`,
      { query, search_type: searchType },
      {
        headers: {
          'X-API-Key': this.config.apiKey
        }
      }
    );

    return response.data;
  }
}

// Moltbot skill registration
export function registerInsightMeshSkill(pi: any) {
  const agent = new InsightMeshAgent({
    apiUrl: process.env.INSIGHTMESH_API_URL!,
    apiKey: process.env.INSIGHTMESH_API_KEY!
  });

  // Register command: /research <query>
  pi.skill({
    name: 'research',
    description: 'Deep research using InsightMesh agents',
    examples: [
      '/research What are the latest trends in AI?',
      '/research Analyze competitor landscape for fintech startups'
    ],
    handler: async (ctx: any) => {
      const query = ctx.args.join(' ');

      if (!query) {
        return ctx.reply('Please provide a research query.');
      }

      // Show typing indicator
      ctx.typing();

      try {
        // Invoke with streaming
        let fullResponse = '';

        await agent.invokeStream(
          {
            query,
            userId: ctx.user.id,
            platform: 'moltbot',
            context: {
              channel: ctx.channel.id,
              message_id: ctx.message.id
            }
          },
          (chunk) => {
            fullResponse += chunk;
            // Update message with streaming content
            ctx.updateReply(fullResponse);
          }
        );

        return ctx.reply(fullResponse);
      } catch (error) {
        return ctx.reply(
          `Research failed: ${error.message}`
        );
      }
    }
  });

  // Register command: /rag <query>
  pi.skill({
    name: 'rag',
    description: 'Query InsightMesh knowledge base',
    handler: async (ctx: any) => {
      const query = ctx.args.join(' ');

      try {
        const results = await agent.ragQuery(
          query,
          ctx.user.id
        );

        let response = `Found ${results.documents.length} relevant documents:\n\n`;

        for (const doc of results.documents.slice(0, 3)) {
          response += `• ${doc.text}\n`;
        }

        return ctx.reply(response);
      } catch (error) {
        return ctx.reply(`RAG query failed: ${error.message}`);
      }
    }
  });

  // Register command: /websearch <query>
  pi.skill({
    name: 'websearch',
    description: 'Search the web via InsightMesh',
    handler: async (ctx: any) => {
      const query = ctx.args.join(' ');
      const searchType = ctx.flags.deep ? 'deep' : 'quick';

      try {
        const results = await agent.webSearch(query, searchType);

        let response = `Web search results:\n\n`;
        for (const result of results.results) {
          response += `• ${result.title}\n  ${result.url}\n\n`;
        }

        return ctx.reply(response);
      } catch (error) {
        return ctx.reply(`Search failed: ${error.message}`);
      }
    }
  });
}
```

## 2.3 Authentication & Security

```python
# agent-service/auth/external_auth.py
from fastapi import HTTPException, Header
import hashlib
import secrets
from datetime import datetime, timedelta

class ExternalAPIAuth:
    """Authentication for external API access"""

    def __init__(self):
        self.api_keys: dict[str, dict] = {}
        self.rate_limits: dict[str, list] = {}

    def generate_api_key(self, client_name: str) -> str:
        """Generate new API key for external client"""
        key = f"im_{secrets.token_urlsafe(32)}"

        self.api_keys[key] = {
            "client": client_name,
            "created": datetime.utcnow(),
            "requests": 0,
            "rate_limit": 100,  # requests per minute
        }

        return key

    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key"""
        return api_key in self.api_keys

    def check_rate_limit(self, api_key: str) -> bool:
        """Check if request is within rate limit"""
        if api_key not in self.rate_limits:
            self.rate_limits[api_key] = []

        now = datetime.utcnow()
        window_start = now - timedelta(minutes=1)

        # Remove old requests
        self.rate_limits[api_key] = [
            ts for ts in self.rate_limits[api_key]
            if ts > window_start
        ]

        # Check limit
        config = self.api_keys[api_key]
        if len(self.rate_limits[api_key]) >= config["rate_limit"]:
            return False

        # Add current request
        self.rate_limits[api_key].append(now)
        config["requests"] += 1

        return True
```

---

# Deployment Strategy

## Option 1: Separate Services (Recommended)

```yaml
# docker-compose.yml
services:
  # InsightMesh services (existing)
  insightmesh-bot:
    build: ./bot
    environment:
      - MULTI_CHANNEL_ENABLED=true
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}

  insightmesh-agent-api:
    build: ./agent-service
    ports:
      - "8000:8000"
    environment:
      - EXTERNAL_API_ENABLED=true
      - API_KEYS=${EXTERNAL_API_KEYS}

  # Moltbot service (separate)
  moltbot:
    build: ./moltbot
    environment:
      - INSIGHTMESH_API_URL=http://insightmesh-agent-api:8000
      - INSIGHTMESH_API_KEY=${INSIGHTMESH_API_KEY}
```

## Option 2: Hybrid (Multi-Channel in InsightMesh, Agents for Moltbot)

```yaml
services:
  # InsightMesh handles Slack, Discord, Telegram natively
  insightmesh-multi:
    build: ./bot
    environment:
      - SLACK_ENABLED=true
      - DISCORD_ENABLED=true
      - TELEGRAM_ENABLED=true

  # Moltbot handles WhatsApp, Signal, Matrix, etc.
  # Calls InsightMesh for agent capabilities
  moltbot:
    build: ./moltbot
    environment:
      - INSIGHTMESH_AGENT_API=http://insightmesh-multi:8000
```

---

# Implementation Timeline

## Week 1-2: Phase 1 Foundation
- ✅ Create base channel adapter interface
- ✅ Implement Discord adapter (proof of concept)
- ✅ Build channel router
- ✅ Test with Discord + Slack

## Week 3-4: Multi-Channel Expansion
- ✅ Implement Telegram adapter
- ✅ Implement WhatsApp adapter (Twilio)
- ✅ Add configuration management
- ✅ Test all channels

## Week 5-6: Phase 2 - External API
- ✅ Create external agent API endpoints
- ✅ Implement authentication & rate limiting
- ✅ Add streaming support
- ✅ Write OpenAPI documentation

## Week 7-8: Moltbot Integration
- ✅ Build moltbot skill/plugin
- ✅ Test integration
- ✅ Deploy both systems
- ✅ Monitor and optimize

---

# Benefits of This Architecture

✅ **Best of Both Worlds**
- Moltbot: Multi-channel expertise
- InsightMesh: Enterprise RAG + agents

✅ **Flexible Deployment**
- Can run separately or integrated
- Mix and match channels

✅ **Maintainable**
- Clear separation of concerns
- Independent scaling

✅ **Future-Proof**
- Easy to add new channels
- API allows other integrations

This gives you enterprise-grade AI across **12+ messaging platforms**! 🚀
