# Tool Use - Setup Guide

## Overview

**Tool Use:** Enabling the model to call external functions and APIs

## Prerequisites

- api_authentication

- system_prompt

## Procedure

### Configure Tool Definitions
To configure tool use, add a tools array to your API request.
Each tool needs a name, description, and input_schema.
Claude will return a tool_use content block when it wants to call a tool.
Your code must execute the tool and return results in a tool_result message.


### Set System Instructions
Add a system parameter to your API request with instructions for Claude.
The system prompt should clearly state Claude's role, any constraints,
preferred output format, and tone. Keep system prompts focused and specific.


## Verification

Tool use allows Claude to call external functions you define.
You provide tool definitions with names, descriptions, and input schemas.
Claude decides when to use a tool and returns a tool_use response block.


## Troubleshooting

Tool use allows Claude to call external functions you define.
You provide tool definitions with names, descriptions, and input schemas.
Claude decides when to use a tool and returns a tool_use response block.

