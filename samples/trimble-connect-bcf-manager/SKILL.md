---
name: trimble-connect-bcf-manager
description: Create and query Building Collaboration Format issue topics in Trimble Connect. Use when a request involves recording, finding, or reviewing BCF coordination issues.
---

# Trimble Connect BCF Manager

Use this skill to create and query BCF issue topics in Trimble Connect.

## Create a topic

1. Identify the Trimble Connect project.
2. Collect a concise title, description, and topic type from the request.
3. Confirm required project or issue details when they are missing.
4. Create the BCF topic with the approved Trimble Connect tool.
5. Return the created topic identifier and a concise summary.

## Query topics

1. Identify the project and any requested filters.
2. Query BCF topics with the approved read tool.
3. Summarize matching topics without inventing missing fields.

## Guardrails

- Use only the Trimble Connect project identified by the request.
- Do not claim that a topic was created unless the tool confirms success.
- Ask for clarification when the project or required topic details are ambiguous.
