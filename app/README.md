# Customer Support Application Reference

This document is the detailed technical reference for the customer support application code in this repository. It covers the runtime behavior, the Strands agent, local and gateway-backed tools, memory and session handling, model configuration, frontend flow, security model, and deployment integration.

## Scope and responsibilities

The application layer is responsible for the actual working behavior of the customer support solution. In contrast to the root project, which defines the AgentCore platform and deployment resources, the code in this directory implements the agent logic and user-facing behavior.

The app includes:

- the runtime entrypoint and streaming request handling
- the Strands agent and system prompt
- built-in business tools for return policy, product lookup, and order lookup
- MCP integrations for external knowledge and gateway-backed actions
- AgentCore memory configuration for user and session context
- the Flask-based browser interface
- model setup and policies for secure tool invocation

In normal operation, the support flow covers order checks, customer information retrieval, refund processing, and context retention across sessions. The runtime also reflects the project’s security model: refund requests of $1,000 or less are allowed, larger requests are denied, prompt injection cannot bypass authorization, and retries do not create duplicate refunds. Several failure scenarios are exercised during testing, and the resulting issues can be traced and diagnosed through telemetry and runtime traces.

## High-level runtime flow

1. The browser authenticates with Cognito and receives a JWT.
2. The frontend calls the deployed AgentCore runtime with that token and a session identifier.
3. The runtime validates the caller and loads the correct session context.
4. The Strands agent decides whether to answer directly or use tools.
5. The agent may consult memory, invoke local tools, or call secure MCP/gateway tools.
6. The response is streamed back to the frontend and displayed to the user.

## Runtime entrypoint

The agent runtime is defined in [CustomerSupport/main.py](CustomerSupport/main.py).

Key responsibilities:

- create a `BedrockAgentCoreApp`
- initialize the Strands agent
- build or reuse a session-scoped agent instance
- decode the JWT to determine the caller identity
- stream model output back to the caller

The main invocation path is:

```python
agent = get_or_create_agent(session_id, user_id, auth_header)
stream = agent.stream_async(payload.get("prompt"))
```

The request handler also requires a valid bearer token in the `Authorization` header and rejects requests that do not include it.

## System prompt and behavior

The runtime defines the agent persona and operational approach in [CustomerSupport/main.py](CustomerSupport/main.py). It tells the agent to:

- act as a helpful customer support assistant
- prefer tool-based answers over guesses
- stay friendly, professional, and concise
- offer follow-up help after resolving a question
- avoid unsupported claims and emojis

This instruction layer helps the model remain grounded in truthful support workflows while still being conversational.

## Model configuration

The model is initialized in [CustomerSupport/model/load.py](CustomerSupport/model/load.py):

```python
BedrockModel(model_id="global.anthropic.claude-sonnet-4-6")
```

This is the model used for reasoning, tool selection, and final response synthesis for the support assistant.

## Built-in tools

The local tool implementations are defined directly in [CustomerSupport/main.py](CustomerSupport/main.py). These are the business-logic tools that support the demo storefront flow.

### `get_return_policy(product_category: str)`

Returns the return policy for a specific category, such as `electronics`, `accessories`, or `audio`. The response includes:

- the return window
- product condition requirements
- refund guidance

### `get_product_info(query: str)`

Searches the in-memory product catalog by:

- product ID
- product name
- keyword
- category match

It returns the product name, price, category, description, and warranty period.

### `get_order(order_id: str)`

Looks up an in-memory order record and returns the status, ordered items, and total.

### Demo data model

The app includes example product and order records used for demonstration and tool testing. The events and return rules simulate a storefront support environment without requiring real backend services.

## MCP integrations

The MCP layer is defined in [CustomerSupport/mcp_client/client.py](CustomerSupport/mcp_client/client.py).

There are two important integrations:

### 1. Web/external search

The agent can attach an Exa MCP client to perform search or retrieval when external information is useful.

### 2. AgentCore gateway access

The app also connects to the AgentCore gateway through an MCP client. This gateway exposes protected Lambda-backed tools and uses the caller's JWT to authorize access. That token-forwarding pattern ensures gateway tools are only called by authenticated, authorized users.

## Memory and session handling

Memory integration is defined in [CustomerSupport/memory/session.py](CustomerSupport/memory/session.py).

The runtime reads `MEMORY_SHAREDMEMORY_ID` from the environment and creates an `AgentCoreMemorySessionManager` when available. Retrieval is configured for:

- user facts: `/users/{actor_id}/facts`
- session summaries: `/summaries/{actor_id}/{session_id}`

This provides the agent with persistent user context and summary memory across turns, which is important for contextual support interactions.

## Authentication and caller identity

The runtime uses a bearer token in the `Authorization` header to determine the user identity. The function `extract_user_id(auth_header)` decodes the JWT without verifying the signature for the sake of the workshop-style demo and reads the `username` claim.

If no valid bearer token is present, the runtime raises an error and stops the request. This makes authentication a gate for access to the agent and its tool usage.

## Security boundary and policy enforcement

This app intentionally separates business capability and security enforcement.

- the agent decides which tool or information to use
- the gateway evaluates protected actions through Cedar policies
- sensitive operations are not allowed without an authorization decision

The project-level policy engine is defined in [../agentcore/agentcore.json](../agentcore/agentcore.json). The gateway includes Lambda-backed operations for warranty checks and refund processing, and the policy statements gate when those tools may run. The support flow is designed so the agent can check orders and customer details, but refund execution remains controlled by policy: refunds at or below $1,000 are allowed, while requests above that threshold are denied. The same design is intended to resist prompt-injection attempts and to prevent duplicate refund execution on retries. In practice, the app also exercises multiple failure scenarios, and the resulting behavior is visible through traces and telemetry for diagnosis.

## Frontend application

The browser-facing interface is implemented in [CustomerSupport/frontend/frontend.py](CustomerSupport/frontend/frontend.py), with the template in [CustomerSupport/frontend/templates/index.html](CustomerSupport/frontend/templates/index.html).

### Responsibilities

- authenticate workshop users with Cognito
- get an access token
- retrieve runtime metadata from the local deployment state
- render the support chat UI and pass runtime information to the browser

### Startup behavior

On startup, the frontend:

- resolves the AWS region
- creates SSM and Cognito clients
- attempts to authenticate the workshop user
- renders the chat page with runtime metadata and token information

## Supporting files and configuration

### Tool schemas

The gateway-backed tool schemas live in:

- [CustomerSupport/tool/warranty_schema.json](CustomerSupport/tool/warranty_schema.json)
- [CustomerSupport/tool/refund_schema.json](CustomerSupport/tool/refund_schema.json)

These files define the input contract for the protected Lambda-based operations.

### Skills

The application includes a small skills module in [CustomerSupport/skills/fetcher.py](CustomerSupport/skills/fetcher.py), which can be extended for reusable support logic or information retrieval tasks.

### Project metadata

The app is configured in the project files at:

- [../agentcore/agentcore.json](../agentcore/agentcore.json)
- [../agentcore/aws-targets.json](../agentcore/aws-targets.json)

These files define the runtime, memory, gateway, policy engine, and AWS deployment targets that power the app.

## Evaluations and observing quality

The root AgentCore config includes online evaluation settings that attach built-in evaluators to the runtime. These monitor:

- goal success rate
- answer correctness
- tool selection accuracy

This helps measure whether the agent is behaving effectively in support scenarios.

## Local development

From the project root, local development generally follows the AgentCore workflow:

```bash
cd app/CustomerSupport
agentcore dev
agentcore invoke --dev "What can you do?"
```

The browser frontend can also be started directly:

```bash
cd app/CustomerSupport/frontend
python frontend.py
```

## Application summary

The application is a complete customer support assistant built around a Strands agent, Bedrock model, memory, frontend, and secure tool gateway. It demonstrates how an agent can answer operational questions, maintain context, call tools responsibly, and protect sensitive operations behind a policy boundary.

For the higher-level platform overview, see [../README.md](../README.md).
