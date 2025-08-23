# Code Story Generation

## Overview

The Code Story prompt is designed to convert any code file into a chronological narrative that follows the program's execution flow. This helps non-technical users understand how code works by translating programming logic into accessible stories.

## Design Principles

1. **Chronological Flow**: Follow the code's execution order, not file organization
2. **Multi-language Support**: Handle mixed languages (Python, HTML, CSS, JavaScript, etc.)
3. **Technical Level**: Scale of 1-10 (configurable, default: 5 - balanced technical/accessible)
4. **Concise Summaries**: Brief, focused explanations per section
5. **Code References**: Clear line/function references without including actual code

## Story Structure

### Format
```
## Chapter [N]: [Title] 
**Code Location**: Lines X-Y, Function: `function_name()` | Class: `ClassName`  
**What Happens**: [2-3 sentence summary of what this section does]
**Why It Matters**: [1 sentence on its role in the bigger picture]
```

### Chapter Ordering
Stories should follow program execution chronologically:
1. **Initialization**: Setup, imports, configuration
2. **Core Classes/Functions**: Main business logic in order of execution
3. **User Interactions**: Event handlers, API endpoints, user flows
4. **Helper Functions**: Utilities called by main flow
5. **Program Entry**: Main execution point

## Multi-Language Handling

For files containing multiple languages:
- **HTML**: Structure and user interface elements
- **CSS**: Styling and layout (group related rules)
- **JavaScript**: Interactive behaviors and logic
- **Python**: Server-side logic and data processing
- **SQL**: Database operations and schema

Group related code blocks together even if they span different languages.

## Technical Level Scaling (1-10)

- **Level 1-3**: No jargon, household analogies
- **Level 4-6**: Basic technical terms with explanation
- **Level 7-10**: Full technical vocabulary, assume programming knowledge

Default Level 5 Example:
- ❌ "Instantiates a SQLite connection object"
- ✅ "Creates a connection to the database file"

## Logical Inefficiency Detection

While creating the story, flag potential issues:
- Redundant operations
- Performance bottlenecks
- Logic that could be simplified
- Security concerns

## Usage Notes

- Stories are meant to be read alongside the code file
- Each chapter should reference specific line numbers/functions
- Focus on the "what" and "why", not the "how"
- Keep technical explanations appropriate to the configured level