# Profile Agent Architecture Diagram

## High-Level Flow

```mermaid
graph TB
    Start([User Query:<br/>'profile Tesla AI needs']) --> Entry[ProfileAgent.run]
    Entry --> Detect[Detect Profile Type<br/>& Focus Area]
    Detect --> Init[Initialize LangGraph<br/>with MemorySaver]
    Init --> Stream[Stream Graph Execution]
    Stream --> Cache[Cache Report<br/>& Metadata]
    Cache --> PDF[Generate PDF<br/>from Markdown]
    PDF --> Upload[Upload to Slack<br/>with Summary]
    Upload --> End([PDF + Executive<br/>Summary Delivered])

    style Start fill:#e1f5ff
    style End fill:#c8e6c9
    style Stream fill:#fff9c4
```

## LangGraph State Machine (6 Nodes + Revision Loops)

```mermaid
graph TB
    Start([START]) --> N1[1. clarify_with_user]

    N1 -->|needs clarification| AskUser([Return Question<br/>to User])
    N1 -->|clear enough| N2[2. write_research_brief]

    N2 --> N3[3. validate_research_brief]

    N3 -->|passes validation| N4[4. research_supervisor<br/>SUBGRAPH]
    N3 -->|fails validation<br/>revision_count < 1| N2
    N3 -->|max revisions<br/>exceeded| N4

    N4 --> N5[5. final_report_generation]

    N5 --> N6[6. quality_control]

    N6 -->|passes quality| End([END])
    N6 -->|fails quality<br/>revision_count < 1| N5
    N6 -->|max revisions<br/>exceeded| Warning[Add Warning<br/>to Report]
    Warning --> End

    style Start fill:#e1f5ff
    style End fill:#c8e6c9
    style N4 fill:#fff9c4
    style AskUser fill:#ffcdd2
    style Warning fill:#ffe0b2
```

## Research Supervisor Subgraph (Parallel Researchers)

```mermaid
graph TB
    SubStart([Supervisor<br/>Subgraph Entry]) --> Sup[Supervisor Node<br/>LLM with ConductResearch tool]

    Sup --> SupTools[Supervisor Tools Node<br/>Execute Delegations]

    SupTools -->|Launch Parallel<br/>Researchers| R1[Researcher 1<br/>Topic A]
    SupTools --> R2[Researcher 2<br/>Topic B]
    SupTools --> R3[Researcher 3<br/>Topic C]

    R1 --> RNode1[Researcher Node<br/>LLM with Tools]
    R2 --> RNode2[Researcher Node<br/>LLM with Tools]
    R3 --> RNode3[Researcher Node<br/>LLM with Tools]

    RNode1 --> RTools1[Researcher Tools Node]
    RNode2 --> RTools2[Researcher Tools Node]
    RNode3 --> RTools3[Researcher Tools Node]

    RTools1 -->|Tool Calls| RT1[Tools:<br/>web_search<br/>scrape_url<br/>internal_search<br/>sec_query<br/>think]
    RTools2 -->|Tool Calls| RT2[Tools:<br/>web_search<br/>scrape_url<br/>internal_search<br/>sec_query<br/>think]
    RTools3 -->|Tool Calls| RT3[Tools:<br/>web_search<br/>scrape_url<br/>internal_search<br/>sec_query<br/>think]

    RT1 --> RComp1[Compress Research]
    RT2 --> RComp2[Compress Research]
    RT3 --> RComp3[Compress Research]

    RComp1 --> Gather[asyncio.gather<br/>Collect All Results]
    RComp2 --> Gather
    RComp3 --> Gather

    Gather --> SupCheck{Supervisor:<br/>More Research<br/>Needed?}

    SupCheck -->|Yes<br/>iterations < 4| Sup
    SupCheck -->|No<br/>ResearchComplete| SubEnd([Supervisor<br/>Subgraph Exit])

    style SubStart fill:#e1f5ff
    style SubEnd fill:#c8e6c9
    style Sup fill:#fff9c4
    style R1 fill:#e1bee7
    style R2 fill:#e1bee7
    style R3 fill:#e1bee7
    style Gather fill:#ffccbc
```

## State Structure

```mermaid
graph TB
    State[ProfileAgentState<br/>TypedDict] --> Input[Input Fields]
    State --> Research[Research Brief]
    State --> Notes[Research Notes]
    State --> Report[Final Report]
    State --> QC[Quality Control]
    State --> Meta[Metadata]

    Input --> |query: str| Q[User's query]
    Input --> |messages: list| M[Conversation history]

    Research --> |research_brief: str| RB[15-30 research questions]
    Research --> |brief_passes_validation: bool| BV[Validation status]
    Research --> |brief_revision_count: int| BR[Revision attempts]

    Notes --> |raw_notes: list| RN[Unprocessed findings]
    Notes --> |notes: list| CN[Compressed findings]
    Notes --> |research_iterations: int| RI[Research rounds]

    Report --> |final_report: str| FR[Markdown report]
    Report --> |executive_summary: str| ES[3-5 bullet summary]

    QC --> |passes_quality: bool| PQ[Quality validation]
    QC --> |revision_count: int| RC[Report revisions]
    QC --> |max_revisions_exceeded: bool| MR[Revision limit flag]

    Meta --> |profile_type: str| PT[company/employee]
    Meta --> |focus_area: str| FA[User's specific focus]

    style State fill:#e1f5ff
```

## Tool Ecosystem

```mermaid
graph TB
    Tools[Research Tools] --> Search[Search Tools]
    Tools --> Internal[Internal Tools]
    Tools --> Structured[Structured Output]

    Search --> T1[web_search<br/>Tavily fast search]
    Search --> T2[scrape_url<br/>Tavily URL scraping]
    Search --> T3[deep_research<br/>Perplexity long-form]

    Internal --> T4[internal_search_tool<br/>Qdrant vector DB]
    Internal --> T5[sec_query<br/>SEC filing search]

    Structured --> T6[ConductResearch<br/>Supervisor delegation]
    Structured --> T7[ResearchComplete<br/>Supervisor signal]
    Structured --> T8[think_tool<br/>Strategic reflection]

    T4 --> Boost[Entity Boosting:<br/>+20% company in content<br/>+30% company in title<br/>-50% index files]

    T5 --> SEC[On-demand:<br/>Latest 10-K<br/>4 recent 8-Ks<br/>Vector similarity search]

    style Tools fill:#fff9c4
    style Search fill:#e1bee7
    style Internal fill:#ffccbc
    style Structured fill:#c8e6c9
```

## Company Profile Structure (9 Sections)

```mermaid
graph TB
    Profile[Company Profile<br/>Markdown Report] --> S1[1. Company Overview<br/>& Financial Position]
    Profile --> S2[2. Company Priorities<br/>Current/Next Year]
    Profile --> S3[3. Technology Stack<br/>Innovation & IP Strategy]
    Profile --> S4[4. Market Position<br/>Industry Trends & Risks]
    Profile --> S5[5. News Stories<br/>Past 12 Months]
    Profile --> S6[6. Executive Team]
    Profile --> S7[7. Relationships<br/>8th Light Network]
    Profile --> S8[8. Competitive Landscape]
    Profile --> S9[9. Size of Teams]

    Profile --> Sources[## Sources<br/>Numbered citations]

    S7 -->|Powered by| Internal[internal_search_tool<br/>Entity Boosting]
    Internal --> Status{Relationship<br/>Status}
    Status --> Existing[Existing client]
    Status --> None[No prior engagement]

    style Profile fill:#e1f5ff
    style S7 fill:#fff9c4
    style Internal fill:#ffccbc
```

## Focus Area Flow (Dynamic Research Emphasis)

```mermaid
graph TB
    Query[User Query:<br/>'profile Tesla AI needs'] --> Extract[extract_focus_area]

    Extract --> Focus[focus_area: 'AI needs']

    Focus --> Brief[Research Brief<br/>Generation]
    Brief --> Alloc[60-70% of questions<br/>focus on AI needs]

    Focus --> Research[Research Phase]
    Research --> Guide[Guide researchers<br/>toward AI topics]

    Focus --> Report[Final Report]
    Report --> Emphasize[Deeper AI sections<br/>Highlighted insights]

    Focus --> Summary[Executive Summary]
    Summary --> Include[AI needs prominently<br/>featured]

    style Query fill:#e1f5ff
    style Focus fill:#fff9c4
    style Alloc fill:#c8e6c9
    style Guide fill:#c8e6c9
    style Emphasize fill:#c8e6c9
    style Include fill:#c8e6c9
```

## Integration Points

```mermaid
graph TB
    User[User in Slack] -->|Message with<br/>'profile' command| Handler[message_handlers.py]

    Handler --> Router[AgentRouter]
    Router --> Registry[agent_registry]
    Registry --> Agent[ProfileAgent.run]

    Agent --> Context[Context Passed]
    Context --> LLM[llm_service]
    Context --> Slack[slack_service]
    Context --> Cache[conversation_cache]
    Context --> Channel[channel + thread_ts]

    Agent --> Services[External Services]
    Services --> Tavily[Tavily Search API]
    Services --> Perplexity[Perplexity API]
    Services --> Qdrant[Qdrant Vector DB]
    Services --> Langfuse[Langfuse Prompts]
    Services --> SEC[SEC EDGAR API]

    Agent --> Output[Output Generation]
    Output --> MD[Markdown Report]
    MD --> PDF[PDF Conversion]
    PDF --> Upload[Slack Upload]
    Upload --> Comment[Executive Summary<br/>as initial_comment]

    style User fill:#e1f5ff
    style Agent fill:#fff9c4
    style Upload fill:#c8e6c9
```

## Validation Gates (Quality Control)

```mermaid
graph TB
    Start([Research Brief<br/>Generated]) --> V1[validate_research_brief]

    V1 --> Check1{Question Count<br/>15-30?}
    Check1 -->|No| Fail1[Revision Loop 1]
    Check1 -->|Yes| Check2

    Check2{Section Coverage<br/>All 9/8 sections?}
    Check2 -->|No| Fail1
    Check2 -->|Yes| Check3

    Check3{Focus Alignment<br/>50-70% if specified?}
    Check3 -->|No| Fail1
    Check3 -->|Yes| Pass1[Proceed to Research]

    Fail1 -->|revision_count < 1| Revise1[write_research_brief<br/>with revision_prompt]
    Fail1 -->|max exceeded| Warn1[Flag max_revisions_exceeded<br/>Proceed anyway]

    Revise1 --> V1
    Warn1 --> Pass1

    Pass1 --> Research[Research Phase]
    Research --> Report[final_report_generation]

    Report --> V2[quality_control]

    V2 --> Check4{Sources Section<br/>5-10+ entries?}
    Check4 -->|No| Fail2[Revision Loop 2]
    Check4 -->|Yes| Check5

    Check5{Focus Area<br/>Alignment?}
    Check5 -->|No| Fail2
    Check5 -->|Yes| Pass2[Complete]

    Fail2 -->|revision_count < 1| Revise2[final_report_generation<br/>with revision_prompt]
    Fail2 -->|max exceeded| Warn2[Add warning to report<br/>Proceed to completion]

    Revise2 --> V2
    Warn2 --> Pass2
    Pass2 --> End([PDF + Summary<br/>Delivered])

    style Start fill:#e1f5ff
    style Pass1 fill:#c8e6c9
    style Pass2 fill:#c8e6c9
    style End fill:#c8e6c9
    style Fail1 fill:#ffcdd2
    style Fail2 fill:#ffcdd2
    style Warn1 fill:#ffe0b2
    style Warn2 fill:#ffe0b2
```

## Configuration & Settings

```yaml
ProfileConfiguration:
  # Parallel Research
  max_concurrent_research_units: 3

  # Research Iterations
  max_researcher_iterations: 4
  max_react_tool_calls: 8

  # Search API
  search_api: TAVILY  # or PERPLEXITY

  # Models
  research_model: "openai:gpt-4o-mini"
  final_report_model: "openai:gpt-4o"
  final_report_model_max_tokens: 60000

  # Behavior
  allow_clarification: false
  pdf_style: PROFESSIONAL  # MINIMAL, PROFESSIONAL, DETAILED
```

## Error Handling & Resilience

```mermaid
graph TB
    Exec[Graph Execution] --> E1{Token Limit<br/>Exceeded?}
    E1 -->|Yes| Retry1[Retry with<br/>truncated history<br/>max 3 attempts]
    E1 -->|No| E2

    Retry1 --> E2{Validation<br/>Failure?}
    E2 -->|Yes| Retry2[Revision Loop<br/>max 1 revision]
    E2 -->|No| E3

    Retry2 --> E3{Quality<br/>Failure?}
    E3 -->|Yes| Retry3[Revision Loop<br/>max 1 revision]
    E3 -->|No| E4

    Retry3 --> E4{Max Revisions<br/>Exceeded?}
    E4 -->|Yes| Warn[Add Warning<br/>Proceed Anyway]
    E4 -->|No| E5

    Warn --> E5{Tool<br/>Error?}
    E5 -->|Yes| Continue[Continue with<br/>Available Data]
    E5 -->|No| Success[Success]

    Success --> Output[Generate Output]
    Continue --> Output

    style Exec fill:#e1f5ff
    style Success fill:#c8e6c9
    style Output fill:#c8e6c9
    style Warn fill:#ffe0b2
```

---

## Key Insights

### 1. **Hierarchical LangGraph Architecture**
- Main graph orchestrates 6 core nodes
- Supervisor subgraph manages parallel researchers
- Each researcher runs its own tool-calling loop

### 2. **Quality Gates with Controlled Revisions**
- Research brief validation (max 1 revision)
- Final report quality control (max 1 revision)
- Graceful degradation if max revisions exceeded

### 3. **Parallel Research for Speed**
- Up to 3 concurrent researchers
- Each focuses on different topics
- Supervisor iterates up to 4 times

### 4. **Entity Boosting for Relationship Detection**
- Prevents false positives (Vail Resorts, Costco cases)
- Prioritizes company-specific documents
- Penalizes generic index files

### 5. **Focus Area Guidance Throughout**
- Extracted once at start
- Influences brief generation (60-70% allocation)
- Guides researchers
- Emphasized in final report
- Featured in executive summary

### 6. **External Prompt Versioning**
- Langfuse integration for prompt management
- Enables A/B testing and iteration
- Centralized prompt control

### 7. **Comprehensive Error Handling**
- Token limit retries
- Validation failures with revision loops
- Tool errors don't block workflow
- Max revision safeguards

### 8. **Stateful Execution with Checkpointer**
- MemorySaver singleton preserves state
- Enables multi-turn conversations
- Thread-level caching for follow-ups
