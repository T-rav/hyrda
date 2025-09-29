# Top 5 Managed Evaluators for System Prompt Testing

Add these Langfuse managed evaluators alongside your 5 custom ones for comprehensive coverage:

## 🎯 **Recommended Managed Evaluators**

### 1. **Helpfulness**
- **What it tests:** How helpful and useful the response is to the user
- **Why important:** Critical for executive productivity and decision support
- **Complements:** Your custom evaluators by ensuring responses are actually useful

### 2. **Conciseness**
- **What it tests:** Whether response is appropriately concise without being too brief
- **Why important:** Executives value time-efficient communication
- **Complements:** Executive readiness by ensuring optimal response length

### 3. **Coherence**
- **What it tests:** Logical flow, consistency, and clarity of the response
- **Why important:** Complex business topics require clear, logical explanations
- **Complements:** Professional tone by ensuring structured communication

### 4. **Correctness**
- **What it tests:** Factual accuracy and logical soundness of information
- **Why important:** Business decisions require accurate information
- **Complements:** Your "accuracy over speculation" evaluator

### 5. **Harmlessness**
- **What it tests:** Ensures responses avoid harmful, inappropriate, or biased content
- **Why important:** Enterprise compliance and professional standards
- **Complements:** Professional tone by catching any inappropriate content

## 📊 **Complete Evaluation Suite (10 Total)**

### Custom Evaluators (5):
1. `professional_tone` - Business communication standards
2. `source_transparency` - Knowledge base vs general knowledge clarity
3. `accuracy_over_speculation` - Intellectual honesty
4. `rag_behavior` - Knowledge retrieval integration
5. `executive_readiness` - Strategic decision support

### Managed Evaluators (5):
6. `helpfulness` - Response utility and value
7. `conciseness` - Optimal response length
8. `coherence` - Logical structure and clarity
9. `correctness` - Factual accuracy
10. `harmlessness` - Professional appropriateness

## 🎯 **Why This Combination Works**

**Custom evaluators** test your **specific system prompt behaviors**
**Managed evaluators** test **universal response quality**

Together they ensure your system prompt produces responses that are:
- ✅ **Behaviorally correct** (follows your prompt instructions)
- ✅ **Universally high-quality** (helpful, clear, accurate, appropriate)

## 🚀 **Setup in Langfuse**

1. **Add your 5 custom evaluators** (from `evaluator_prompts.md`)
2. **Add these 5 managed evaluators** from the Langfuse catalog
3. **Run evaluation** with all 10 against your `system-prompt-evaluation` dataset
4. **Target scores:**
   - Custom evaluators: ≥4.0 average
   - Managed evaluators: ≥4.2 average
   - Overall: ≥4.1 average

## 📈 **Success Criteria**

**🟢 Excellent (≥4.5):** Production ready, exceptional quality
**🟡 Good (≥4.0):** Production ready with minor optimization potential
**🟠 Needs Work (≥3.5):** Requires prompt improvements before production
**🔴 Poor (<3.5):** Significant prompt revision needed

This comprehensive 10-evaluator suite gives you enterprise-grade system prompt validation! 🎉
