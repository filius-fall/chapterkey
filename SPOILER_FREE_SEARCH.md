# Spoiler-Free Search Feature

## 📖 Read Without Spoilers!

Now you can limit book searches to only include content you've already read - perfect for avoiding spoilers while reading EPUBs!

## 🎯 Features

### Full Search (Default)
Searches the **entire book** - any content is fair game.

**Use when:**
- You've finished the book
- You don't care about spoilers
- You need comprehensive information

### Limited Knowledge Search (NEW!)
Searches **only up to a certain point** in the book - content beyond that is excluded.

**Use when:**
- You're currently reading and want to avoid spoilers
- You want to test comprehension of what you've read
- You're following a reading schedule

## 🔧 Three Ways to Limit Search

### 1. By Progress Percentage (Recommended)

Limit search to first X% of the book.

**Example:** You've read 50% of the book
```json
{
  "question": "What is the main plot so far?",
  "progress_percent": 50
}
```

**How it works:**
- Calculates which chapters fall within the first 50%
- Only searches those chapters
- Answers based ONLY on that content

**Best for:**
- Reading progress tracking
- Gradual comprehension testing
- Scheduled reading plans

### 2. By Chapter Limit

Limit search to content **before** a specific chapter.

**Example:** You're about to start "Chapter 10"
```json
{
  "question": "Who are the main characters?",
  "chapter_limit": "Chapter 10"
}
```

**How it works:**
- Finds chapter by name
- Includes all content BEFORE that chapter
- Excludes the specified chapter and everything after

**Best for:**
- Specific stopping points
- Testing comprehension before moving forward
- Avoiding spoilers for upcoming content

### 3. By Chunk Count

Limit search to the first N chunks from the start of the book.

**Example:** Include first 100 chunks
```json
{
  "question": "What happens in the beginning?",
  "chunk_count": 100
}
```

**How it works:**
- Simply takes first N chunks
- Simple and predictable
- Good for rough estimates

**Best for:**
- Rough progress tracking
- Quick tests
- When you don't know exact percentage

## 📝 Important Rules

### Only ONE Limit Option
You can use **only one** limit method at a time:

❌ **Wrong:** Multiple limits
```json
{
  "progress_percent": 50,
  "chapter_limit": "Chapter 10"
}
```

✅ **Correct:** Single limit
```json
{
  "progress_percent": 50
}
```

### No Limit = Full Search

Omit all limit parameters to search the entire book:
```json
{
  "question": "What is the main theme?"
}
```

## 🚀 Usage Examples

### ask_question (Returns passages for Claude Code)

**Full search:**
```json
{
  "question": "What are the main themes?"
}
```

**Limited search (50%):**
```json
{
  "question": "What has happened so far?",
  "progress_percent": 50
}
```

**Limited search (before Chapter 15):**
```json
{
  "question": "Who are the protagonists?",
  "chapter_limit": "Chapter 15"
}
```

**Limited search (first 50 chunks):**
```json
{
  "question": "What's the setting like?",
  "chunk_count": 50
}
```

### ask_question_with_llm (Uses Gemini to generate answer)

**Full search:**
```json
{
  "question": "What are the main themes?",
  "model": "google/gemini-2.5-flash-preview"
}
```

**Limited search (75%):**
```json
{
  "question": "What's the plot development?",
  "progress_percent": 75,
  "model": "google/gemini-2.5-flash-preview"
}
```

## 📊 How It Works

### With Progress Percent
```
Book: 100 chapters total
Progress: 50%
Limit: Chapters 0-49 (first 50 chapters)
Search: Only these 49 chapters
Answer: Based only on chapters 0-49
```

### With Chapter Limit
```
Book: Chapter 1 to Chapter 20
Limit: Before "Chapter 10"
Search: Chapters 1-9
Answer: Based only on chapters 1-9
```

### With Chunk Count
```
Book: 500 chunks total
Limit: First 100 chunks
Search: Chunks 0-99
Answer: Based only on chunks 0-99
```

## 🎓 Use Case Examples

### Scenario 1: Reading Progress Check
You've read 40% of a book and want to check your understanding.

```json
{
  "question": "What are the main conflicts so far?",
  "progress_percent": 40
}
```

### Scenario 2: Before Plot Twist
You're about to read a chapter with a major plot twist and want to avoid spoilers.

```json
{
  "question": "What hints are there about the villain?",
  "chapter_limit": "The Revelation"
}
```

### Scenario 3: Character Development
You want to track how characters have developed through the first 30% of the book.

```json
{
  "question": "How does the protagonist change?",
  "progress_percent": 30
}
```

### Scenario 4: Series Progress
You're reading book 3 of a series and want to avoid spoilers for books 4-6.

```json
{
  "question": "What loose ends from previous books are addressed?",
  "progress_percent": 100
}
```
*(For this case, use progress_percent: 100 since you're asking about a single book)*

## ⚠️ What Happens With Limits

### LLM is Informed
When you use a search limit:
1. The LLM is told about the limit
2. It's instructed to base answers **only** on provided passages
3. No information from beyond the limit is considered

### Search Results Filtered
Only chunks within the limit are:
- Retrieved from the vector database
- Included in the answer
- Used for generating responses

### Clear Indicators
The response clearly shows:
- What limit was applied
- How much of the book was searched
- Warning that answer is limited

## 💡 Tips

### Choose the Right Limit Method

| Situation | Best Method | Why |
|-----------|--------------|------|
| You know your progress (e.g., 50%) | `progress_percent` | Most intuitive |
| You're at a specific chapter | `chapter_limit` | Precise stopping point |
| Rough estimate of progress | `chunk_count` | Quick and easy |

### Gradual Testing
As you read more, increase your limit:
- Start: `progress_percent: 25`
- After reading: `progress_percent: 50`
- Continue: `progress_percent: 75`
- Finish: No limit (full search)

### Avoid Over-Limiting
Don't set limits too low or you might miss relevant context:
- ❌ `progress_percent: 10` (too restrictive)
- ✅ `progress_percent: 50` (reasonable)
- ✅ `progress_percent: 100` (full search)

## 🔍 Verification

When using limits, verify the search scope:

**Output will show:**
```
## Query Summary
- **Search Limit:** First 50% of book (chapters 0-12 of 25)
- **⚠️ Note:** Answer based ONLY on content within limit (no spoilers)
```

This confirms your answers are spoiler-free!

## 🎉 Summary

- ✅ **Full search** - No limit, entire book
- ✅ **Progress percent** - Limit to first X% (most common)
- ✅ **Chapter limit** - Limit before specific chapter
- ✅ **Chunk count** - Limit to first N chunks
- ✅ **Clear warnings** - Always know when limits are applied
- ✅ **No spoilers** - Read confidently without fear of spoilers!

Perfect for book clubs, reading challenges, and personal reading progress tracking! 📚
