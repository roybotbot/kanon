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

Verify the following hold true:

- **Max tools per request**: 128


Confirm these tasks complete successfully:

- [ ] Configure Tool Definitions: Define function schemas that Claude can invoke during a conversation

- [ ] Set System Instructions: Configure a system prompt to control Claude's behavior in a conversation

## Troubleshooting

### Configure Tool Definitions

If configure tool definitions fails, check each step:

  1. Verify: Define the tool name and description

  2. Verify: Specify the input schema using JSON Schema

  3. Verify: Register the tool in the API request tools array

  4. Verify: Handle the tool_use response block

### Set System Instructions

If set system instructions fails, check each step:

  1. Verify: Write a system prompt defining Claude's role and constraints

  2. Verify: Include the system prompt in the API request

  3. Verify: Test with sample conversations to verify behavior
