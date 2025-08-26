# Workflows

## Initial Setup
1. Gmail auth
2. Fetch 12 months metadata (background job)
3. LLM analyzes all metadata → populates subscriptions table

## Ongoing Processing
1. Fetch recent emails
2. LLM decides which domains need content analysis
3. Fetch content for selected domains
4. LLM analyzes content → updates subscriptions

## MCP Tools Needed
- `get_email_metadata`
- `get_email_content` 
- `get_subscriptions`
- `update_subscription`
- `create_subscription`