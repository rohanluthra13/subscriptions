# Workflows

## Initial Setup

1. Download app
2. Connect gmail
    - How: App GUI to browser authentication 
    - Dependencies: Gmail authentication API [DONE]
    - Decisions made: keep to gmail only for MVP
    - Next steps: None
3.  Fetch metadata
    - How: App GUI trigger (button) and MCP tool trigger (Claude desktop) - right now limited to 12 months 
    - Dependencies: Gmail metadata API [DONE]
    - Decisions made: fetch metadata for 12 months 
    - Next steps:
        - Trigger automatically after authentication (for 12 months)
        - Extend user customability to go further back (or less)
4. Manual entry
    - How: App GUI; table + input form
    - Dependencies: editable table + input form in GUI [DOING]
    - Decisions made: this is the bare minimum - status quo options have this already e.g. enter into Excel
    - Next steps:
        - Build into GUI; manage subscription tabs

## Identify current subscriptions / LLM discovery & input


1. Write 'braindump' to notes
    - How: User uses app GUI to write in notepad
    - Dependencies: input form in GUI [DONE]
    - Decisions made: optional step to give more context to LLM
    - Next steps: None

    ### Microagent ###

2. 



## Ongoing management

1. MCP trigger to analyse new emails w/ content for relevant information, save to file for user review
    - How: automate gmail fetch, both metadata and content, then use an mcp prompt to trigger desktop app analysis
    - Dependencies: Gmail API automation (fetch every 'x' hours), mcp prompt (and underlying resources and tools)
    - Next steps:
        - Gmail API automation
        - Define MCP prompt and required resources and tools (to scope work required)
            - Prompt inputs: subscriptions table, 'context' md file (resource)
            - Tools required: read database, edit database 