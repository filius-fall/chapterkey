# Gemini LLM Integration (Gemini-Only)

## ✅ Optimized for Google Gemini Models Only

The server now uses **only Google Gemini models** for question answering - optimized for performance, cost, and quality.

## 🎯 Default Model: Gemini 2.5 Flash Preview

**Model:** `google/gemini-2.5-flash-preview`

**Why it's the default:**
- ✅ **Latest** - Most recent Gemini model (as of March 2026)
- ✅ **Fastest** - Sub-second response times
- ✅ **Cost-effective** - Low cost per token (~₹0.83 per 1M output tokens)
- ✅ **High quality** - Excellent reasoning capabilities
- ✅ **Best value** - Perfect balance of speed, quality, and cost

## 🆕 Available Gemini Models

### 1. `google/gemini-2.5-flash-preview` (DEFAULT) ⭐
- **Latest model** - Most recent Gemini release
- **Speed:** Very Fast ⚡⚡⚡
- **Quality:** High
- **Cost:** ~₹0.83 per 1M output tokens
- **Best for:** Fast answers, general questions, daily use
- **Recommended:** ✅ Yes - Best overall value

### 2. `google/gemini-2.5-pro`
- **Premium model** - Highest quality Gemini
- **Speed:** Fast ⚡⚡
- **Quality:** Very High 🎯
- **Cost:** ~₹2.50 per 1M output tokens
- **Best for:** Complex analysis, detailed research, premium answers

### 3. `google/gemini-1.5-flash`
- **Reliable model** - Proven, stable
- **Speed:** Fast ⚡
- **Quality:** High
- **Cost:** ~₹0.25 per 1M output tokens
- **Best for:** General use, balanced performance

### 4. `google/gemini-1.5-pro`
- **High-quality model** - Excellent reasoning
- **Speed:** Medium
- **Quality:** Very High
- **Cost:** ~₹1.67 per 1M output tokens
- **Best for:** Complex questions, detailed answers

### 5. `google/gemini-1.5-flash-8b`
- **Cheapest model** - Smallest, most cost-effective
- **Speed:** Very Fast ⚡⚡
- **Quality:** Good
- **Cost:** ~₹0.08 per 1M output tokens
- **Best for:** Simple questions, maximum cost savings

## 💰 Cost Comparison (1M Output Tokens)

| Model | Cost (INR) | Speed | Quality |
|-------|-------------|--------|---------|
| **2.5 Flash Preview** (default) | ~₹0.83 | Very Fast | High ⭐ |
| 2.5 Pro | ~₹2.50 | Fast | Very High |
| 1.5 Flash | ~₹0.25 | Fast | High |
| 1.5 Pro | ~₹1.67 | Medium | Very High |
| 1.5 Flash-8B | ~₹0.08 | Very Fast | Good |

**Recommendation:** Use the default `2.5 Flash Preview` - it's the best balance of cost, speed, and quality!

## 📝 Usage

### Default (Recommended)
```json
{
  "question": "What is the main plot?",
  "epub_name": "Optional"
}
```

Uses `google/gemini-2.5-flash-preview` automatically.

### Custom Model
```json
{
  "question": "What is the main plot?",
  "model": "google/gemini-2.5-pro"
}
```

### Cheapest Option
```json
{
  "question": "Who is the protagonist?",
  "model": "google/gemini-1.5-flash-8b"
}
```

### Highest Quality
```json
{
  "question": "Analyze the themes deeply...",
  "model": "google/gemini-2.5-pro"
}
```

## 🔄 Embeddings

For embeddings (vector storage), we use:
- **Model:** `openai/text-embedding-3-small`
- **Cost:** ~₹0.03 per 1M tokens
- **Reason:** Most cost-effective embedding model available via OpenRouter
- **Note:** OpenRouter doesn't offer Gemini embedding models yet

## 🚀 Quick Example

```bash
# Load EPUB
load_epub("/path/to/book.epub")

# Ask with default Gemini 2.5 Flash (recommended)
ask_question_with_llm(
  "What are the main themes?"
)

# Ask with cheaper option
ask_question_with_llm(
  "Who are the characters?",
  model="google/gemini-1.5-flash-8b"
)

# Ask with premium option
ask_question_with_llm(
  "Analyze the symbolism...",
  model="google/gemini-2.5-pro"
)
```

## 📋 Configuration

Default model is set in `.env`:
```bash
LLM_MODEL=google/gemini-2.5-flash-preview
```

You can change this to any Gemini model:
```bash
LLM_MODEL=google/gemini-1.5-flash-8b  # Cheapest
LLM_MODEL=google/gemini-2.5-pro        # Highest quality
```

## ✨ Summary

- **Gemini-only** - Optimized for Google's models
- **Default: 2.5 Flash Preview** - Latest, fastest, best value
- **5 options** - From cheapest to highest quality
- **Cost-effective** - Start at ~₹0.08 per 1M tokens
- **Fast** - Sub-second response times
- **High quality** - Excellent reasoning across all models

Use `list_available_models` to see all Gemini options with descriptions!
