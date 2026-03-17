# Setup Guide: Tool Use with Claude API

**Audience:** Backend Engineers (Enterprise)
**Difficulty:** Intermediate
**Assumed Knowledge:** API authentication with Claude

---

## Overview

Tool use enables Claude to interact with external functions and APIs that you define. Rather than responding purely with text, Claude can identify when a user request requires calling an external function, return a structured `tool_use` response block, and allow your backend to execute the function and return results back into the conversation.

This guide walks through configuring tool definitions, setting appropriate system instructions, and verifying that your integration handles the tool call lifecycle correctly.

**Key concepts:**

- You define the tools — Claude decides when to use them.
- Tool definitions include a name, description, and JSON Schema for inputs.
- The conversation loop must handle `tool_use` response blocks and return results via a `tool_result` message.

---

## Prerequisites

Before beginning, confirm the following are in place:

| Requirement | Details |
|---|---|
| **API Authentication** | You have valid credentials and can successfully authenticate against the Claude API. |
| **System Prompt Access** | Your API request structure supports a `system` parameter. |
| **JSON Schema Familiarity** | You can define input schemas using JSON Schema syntax, as this is required for tool definitions. |
| **Backend Execution Environment** | Your application can execute arbitrary functions/calls and re-inject results into an API request. |

> **Note:** Tool use depends on both `api_authentication` and `system_prompt` being operational. Do not proceed if either prerequisite is unverified.

---

## Procedure

### Step 1: Write a System Prompt

Configure a system prompt to establish Claude's role and behavioral constraints within your application context. A focused, specific system prompt improves tool-use accuracy.

1. Write a system prompt that clearly defines:
   - Claude's role in your application
   - Any constraints on behavior or scope
   - Preferred output format and tone
2. Add a `system` parameter to your API request body containing this prompt.
3. Keep the system prompt focused — avoid combining unrelated instructions.

**Checklist:**
- [ ] Role and purpose are clearly stated
- [ ] Constraints are explicit
- [ ] System prompt is included in the API request

---

### Step 2: Define Your Tools

Each tool must have three components: a **name**, a **description**, and an **input schema**.

1. **Define the tool name and description**
   - The name should be a concise identifier for the function.
   - The description should explain what the tool does and when Claude should use it. This is critical — Claude relies on the description to decide whether to invoke the tool.

2. **Specify the input schema using JSON Schema**
   - Define all parameters the tool accepts, including types and which are required.
   - Be precise; ambiguous schemas can produce malformed tool calls.

3. **Register the tool in the API request**
   - Add a `tools` array to your API request body.
   - Each entry in the array should contain the `name`, `description`, and `input_schema` fields.

**Checklist:**
- [ ] Each tool has a unique, descriptive name
- [ ] Descriptions clearly communicate intended use
- [ ] Input schemas cover all required and optional parameters
- [ ] `tools` array is present in the API request

---

### Step 3: Handle the `tool_use` Response Block

When Claude determines a tool should be called, it returns a `tool_use` content block in its response rather than a plain text reply.

1. **Detect the `tool_use` content block** in the API response.
2. **Extract the tool name and input arguments** from the block.
3. **Execute the corresponding function** in your backend using the provided arguments.
4. **Return the result** to the conversation by sending a `tool_result` message back to the API.
5. **Continue the conversation loop** — Claude will process the tool result and generate its final response.

**Checklist:**
- [ ] Response parsing handles `tool_use` blocks
- [ ] Tool execution logic is mapped to tool names
- [ ] Results are formatted and returned as `tool_result` messages
- [ ] Conversation loop continues after tool result is submitted

---

## Verification

Use the following checks to confirm your tool use integration is functioning correctly end-to-end:

| Check | Expected Outcome |
|---|---|
| Send a request that clearly requires a tool | Claude returns a `tool_use` content block, not a plain text response |
| Inspect the `tool_use` block | Contains the correct tool name and well-formed input arguments matching your schema |
| Submit a `tool_result` message | Claude processes the result and returns a coherent final response |
| Send a request that does NOT require a tool | Claude responds with plain text only — no spurious `tool_use` blocks |
| Test with an ambiguous request | Verify Claude's tool selection aligns with your description intent |

If all checks pass, your integration is correctly handling the full tool call lifecycle.

---

## Troubleshooting

### Claude is not calling the tool when expected

- **Review the tool description.** Claude uses the description to determine relevance. If the description is vague or incomplete, Claude may not recognize when the tool applies. Make it explicit about the scenarios in which the tool should be used.
- **Check the system prompt for conflicts.** If the system prompt contains constraints that inadvertently restrict tool use, Claude may suppress tool calls. Review for contradictory instructions.

---

### Claude is calling the tool when it should not be

- **Tighten the tool description.** Overly broad descriptions can cause Claude to invoke tools unnecessarily. Scope the description to specific, intended use cases.
- **Add explicit guidance in the system prompt** clarifying when tools should and should not be used.

---

### The `tool_use` block contains unexpected or malformed inputs

- **Review your `input_schema` definition.** Ambiguous or loosely typed schemas can result in Claude generating inputs that do not match your expected format. Add stricter type constraints and mark fields as required where appropriate.

---

### Tool results are not being processed by Claude

- **Verify the `tool_result` message format.** Ensure the result is being returned as a properly structured message in the conversation. If the format is incorrect, Claude may not recognize it as a tool response.
- **Check the conversation turn order.** Tool results must be submitted before Claude can generate a follow-up response. Verify your conversation loop is sequencing messages correctly.

---

### Authentication errors during tool use requests

- **Confirm prerequisites are met.** Tool use requires API authentication to be fully functional. Re-verify your credentials and authentication flow before debugging tool-specific behavior.

---

*For additional coverage of advanced tool use patterns, consider adding further entities to your knowledge graph.*