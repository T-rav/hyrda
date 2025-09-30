# System Prompt Evaluation with Langfuse

This directory contains evaluation infrastructure for testing the **Insight Mesh system prompt** using Langfuse's native LLM-as-a-Judge capabilities.

## 🎯 What This Tests

Your system prompt defines 5 core behaviors that we evaluate:

1. **Professional Communication** - Executive-appropriate tone and language
2. **Source Transparency** - Clear indication of information sources (knowledge base vs general)
3. **Accuracy Over Speculation** - Intellectual honesty, acknowledging limitations
4. **RAG Behavior** - Knowledge base prioritization and document retrieval
5. **Executive Readiness** - Strategic insights suitable for decision-making

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd evals
pip install -e .
```

### 2. Setup Environment

```bash
# Make sure these are in your .env file:
LANGFUSE_PUBLIC_KEY=pk_your_key
LANGFUSE_SECRET_KEY=sk_your_key
LANGFUSE_HOST=https://cloud.langfuse.com  # optional
```

### 3. Create Evaluation Infrastructure

```bash
python setup_langfuse_evals.py
# OR using the installed script:
setup-evals
```

### 4. Configure Evaluators in Langfuse

1. **Use `evaluator_prompts.md`** - Copy-paste the 5 custom evaluator configurations
2. **Add managed evaluators** - Use `managed_evaluators.md` for the recommended 5
3. **Set scoring format** - All use: "Return a single integer from 1 to 5 where 1 is poor and 5 is great."

This creates:
- **Dataset**: `system-prompt-evaluation` with 12 test cases
- **Evaluator Configurations**: JSON configs for 5 LLM-as-a-Judge evaluators
- **Test Cases**: Covering all core behaviors from your system prompt

### 3. Set Up Evaluators in Langfuse

After running the setup script:

1. **Go to your Langfuse dashboard**
2. **Navigate to "Evaluations" → "Evaluators"**
3. **Create 5 new evaluators** using the configurations from `evaluator_configs.json`:

   - `professional_tone`
   - `source_transparency`
   - `accuracy_over_speculation`
   - `rag_behavior`
   - `executive_readiness`

4. **Configure each evaluator**:
   - **Type**: LLM-as-a-Judge
   - **Model**: `gpt-4o` (recommended for judging)
   - **Template**: Copy from the corresponding config
   - **Output**: Score (1-5 scale)

### 4. Run Evaluations

In Langfuse dashboard:

1. **Go to "Datasets" → "system-prompt-evaluation"**
2. **Click "Run Evaluation"**
3. **Select your 5 evaluators**
4. **Choose your prompt**: `System/Default`
5. **Run the evaluation**

### 5. View Results

Results appear in the Langfuse dashboard under "Evaluations":
- **Individual scores** for each test case
- **Aggregate metrics** across all evaluators
- **Detailed reasoning** from LLM judges
- **Trend analysis** over time

## 📊 Test Cases Overview

| Test Case | Category | Tests For |
|-----------|----------|-----------|
| `professional_tone_roadmap` | Professional Communication | Business-appropriate language |
| `q3_metrics_rag` | RAG Behavior | Knowledge base search & citation |
| `contract_confidentiality` | Accuracy Over Speculation | Limitation acknowledgment |
| `remote_work_policy_rag` | RAG Behavior | Internal document prioritization |
| `sales_projections_citation` | Source Transparency | Detailed attribution |
| `conversation_context` | Slack Integration | Thread continuity |
| `multi_document_analysis` | RAG Behavior | Cross-reference capability |
| `strategic_guidance` | Executive Readiness | Business decision support |
| `knowledge_base_management` | RAG Behavior | Document ingestion awareness |
| `unavailable_info_handling` | Accuracy Over Speculation | Graceful limitation handling |
| `time_sensitive_request` | Slack Integration | Efficient executive response |
| `executive_decision_support` | Executive Readiness | Strategic analysis delivery |

## 🎯 Success Criteria

**Excellent Performance**: Average score ≥ 4.0 across all evaluators
**Good Performance**: Average score ≥ 3.5 across all evaluators
**Needs Improvement**: Average score < 3.5

### Expected Behaviors by Category:

**Professional Tone (Target: 4.5+)**
- Executive-appropriate language
- Business-focused communication
- Accessible but professional

**Source Transparency (Target: 4.0+)**
- Clear knowledge base vs general knowledge indication
- Appropriate source attribution
- Transparent about limitations

**Accuracy Over Speculation (Target: 4.5+)**
- Intellectual honesty
- Acknowledges uncertainties
- Avoids potentially misleading information

**RAG Behavior (Target: 4.0+)**
- Demonstrates knowledge base search
- Prioritizes organizational documents
- Shows document retrieval understanding

**Executive Readiness (Target: 4.0+)**
- Strategic insights
- Decision-support quality
- Business context awareness

## 🔄 Continuous Improvement

### Iteration Cycle:

1. **Run evaluations** → Get baseline scores
2. **Analyze failures** → Identify prompt weaknesses
3. **Update prompt** → Edit `System/Default` template in Langfuse
4. **Re-run evaluations** → Measure improvement
5. **Deploy** → Update production prompt

### Common Improvements:

**Low Professional Tone**: Add more specific language guidelines
**Low Source Transparency**: Strengthen source indication requirements
**Low RAG Behavior**: Enhance knowledge base search instructions
**Low Executive Readiness**: Add more business context guidance

## 🛠 Advanced Usage

### Custom Test Cases

Add new test cases to the dataset:

```python
# In setup_langfuse_evals.py, add to _get_test_cases():
{
    "input": "Your custom test input",
    "expected_output": {
        "behavior": "Expected behavior description"
    },
    "metadata": {
        "test_name": "custom_test",
        "category": "your_category",
        "expected_behaviors": ["relevant_evaluators"]
    }
}
```

### A/B Testing Prompts

1. Create variant: `System/Variant-A`
2. Run evaluations on both prompts
3. Compare results in Langfuse
4. Deploy the better-performing version

### Monitoring Production

Set up **automatic evaluations** in Langfuse:
- Run weekly against production traces
- Alert on score degradation
- Track performance trends

## 📈 Integration with Development

### Development Setup:

```bash
# Install with dev dependencies
cd evals
pip install -e ".[dev]"

# Format code
black .
ruff check . --fix

# Run tests (if you add any)
pytest
```

### Pre-deployment Checks:

```bash
# Before updating System/Default prompt:
python setup_langfuse_evals.py  # Ensure dataset is current
# → Run evaluation in Langfuse dashboard
# → Ensure all scores > 3.5 before deploying
```

### CI/CD Integration:

Use Langfuse API to run evaluations automatically:
- On prompt template changes
- Before production deployments
- As part of release testing

## 🎉 Success!

With this setup, you have:

✅ **Comprehensive testing** of all system prompt behaviors
✅ **LLM-as-a-Judge evaluation** using GPT-4o for consistent scoring
✅ **Langfuse integration** for tracking, trends, and management
✅ **Continuous improvement** cycle for prompt optimization
✅ **Production monitoring** capability for ongoing quality assurance

Your system prompt evals are now enterprise-ready! 🚀
