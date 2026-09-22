# Customer Support Application Reference

This document is the detailed technical reference for the customer support application code under [app/CustomerSupport](.). It explains how the runtime, tools, memory, model, frontend, and external integrations work together in the deployed AgentCore solution.

## Application scope

The application is a Strands-based customer support assistant for an e-commerce storefront. The runtime exposes a single HTTP entrypoint, authenticates callers with a Cognito JWT, initializes model and memory context, and orchestrates local and external tool calls. The frontend is a lightweight Flask interface that authenticates the browser and calls the deployed runtime.

## Runtime and request flow

The runtime entrypoint is in [main.py](main.py). It performs the following steps:

1. Creates a `BedrockAgentCoreApp` instance.
2. Builds the Strands agent with the configured Bedrock model.
3. Creates a memory-backed session manager using the user and session identifiers.
4. Extracts the caller identity from the `Authorization` header.
5. Streams the agent output back to the caller as the prompt is processed.

The agent is created lazily through `get_or_create_agent(session_id, user_id, auth_header)` and is re-used within the process. The runtime then calls:

```python
stream = agent.stream_async(payload.get("prompt"))
```

and yields the text chunks from the response stream.

## Model configuration

The model is initialized in [model/load.py](model/load.py):

```python
BedrockModel(model_id="global.anthropic.claude-sonnet-4-6")
```

This keeps the agent grounded in Amazon Bedrock and allows the system prompt to steer behavior, tool usage, and reply style.

## System prompt and behavior

The runtime uses a system prompt embedded in [main.py](main.py) to define the agent role and operating constraints:

- act as a helpful customer support assistant
- use tools to answer accurately instead of guessing
- stay friendly, professional, and concise
- offer follow-up help when appropriate
- avoid emojis and unsupported claims

This prompt establishes the support persona and encourages tool-first reasoning.

## Built-in tools

The local tool implementations are defined directly in [main.py](main.py). They are exposed to the agent as Strands tools and provide the business-logic layer for demo support scenarios.

### `get_return_policy(product_category: str)`

Returns the return policy for a product category such as `electronics`, `accessories`, or `audio`.

### `get_product_info(query: str)`

Searches the in-memory product catalog by product ID, product name, or keyword. It returns product details including name, price, category, description, and warranty length.

### `get_order(order_id: str)`

Looks up a demo order record and returns order status, items, and totals.

### Demo data model

The runtime maintains in-memory dictionaries for:

- product catalog
- return-policy rules
- sample orders

Examples include product IDs such as `PROD-001`, `PROD-002`, and `PROD-005`, and order IDs such as `ORD-12345`, `ORD-67890`, and `ORD-54321`.

## MCP integrations

The MCP client layer is defined in [mcp_client/client.py](mcp_client/client.py).

### Web and external search

The runtime attaches an Exa MCP client to the agent so it can retrieve up-to-date information when needed.

### AgentCore gateway integration

A second MCP client connects the runtime to the secure AgentCore gateway. It forwards the caller JWT in the Authorization header so the gateway can authorize access to protected tools before execution.

These MCP clients are added to the agent tool list when building the session-specific runtime.

## Memory system

Memory configuration is provided in [memory/session.py](memory/session.py).

The runtime reads `MEMORY_SHAREDMEMORY_ID` from the environment and creates an `AgentCoreMemorySessionManager` when a memory-backed session is available. The retrieval configuration includes:

- `/users/{actor_id}/facts` for user facts
- `/summaries/{actor_id}/{session_id}` for conversation summaries

This allows the agent to preserve user-specific context and summarize the interaction history across turns.

## Authentication and identity

The runtime validates the caller identity by decoding the bearer token from the `Authorization` header. The function `extract_user_id(auth_header)` checks the JWT claims and extracts the `username` value as the user identifier when present.

If the header is missing, the runtime raises an exception and rejects the request.

This ensures that the request context is tied to a real authenticated user and that memory and access decisions are scoped appropriately.

## Gateway-backed tools and policy enforcement

The project uses an AgentCore gateway and Cedar policies for sensitive operations, especially warranty and refund actions.

The gateway configuration is defined in [agentcore/agentcore.json](../../agentcore/agentcore.json). It includes two Lambda-backed targets:

- `WarrantyCheck`
- `ProcessRefund`

The gateway uses a custom JWT authorizer and an enforcement policy engine. The policy rules in the same config define which operations are allowed under which conditions.

For example:

- refunds are permitted only when the requested amount is below a threshold
- warranty checks are allowed for authenticated users

This checkpoint prevents the agent from invoking protected business functions without a policy decision.

## Frontend application

The browser-based UI is implemented in [frontend/frontend.py](frontend/frontend.py). It uses Flask to provide a lightweight chat interface backed by the deployed runtime.

### Responsibilities

- authenticate workshop users with Cognito
- obtain an access token
- read the deployed runtime ARN from the local AgentCore state file
- render the UI template with the token and runtime metadata

### Template

The UI is defined in [frontend/templates/index.html](frontend/templates/index.html). It shows:

- the conversation interface
- a runtime endpoint view
- the signed-in user identity
- the token context used to call the AgentCore runtime

### Local startup

The app can be started directly with:

```bash
cd app/CustomerSupport/frontend
python frontend.py
```

or through the project-level AgentCore workflow when using the full runtime environment.

## Deployment and runtime configuration

The root deployment configuration in [../../agentcore/agentcore.json](../../agentcore/agentcore.json) defines the runtime and gateways for the application. Key settings include:

- runtime name and entrypoint
- code location
- Python runtime version
- HTTP protocol configuration
- allowlisted request headers
- custom JWT authorizer settings
- memory resource strategy definitions
- policy engine attachment and tool targets

This is the infrastructure contract for the app; the Python code under the app folder implements the behavior that those resources support.

## Evaluations and quality monitoring

The root config includes an online evaluation setup named `QualityMonitor` in [../../agentcore/agentcore.json](../../agentcore/agentcore.json). This config attaches built-in evaluators:

- `Builtin.GoalSuccessRate`
- `Builtin.Correctness`
- `Builtin.ToolSelectionAccuracy`

These evaluators help monitor whether the runtime is satisfying customer support goals and using tools correctly.

## Security model

The application uses multiple layers of security:

- Cognito-issued JWTs for authenticated frontend access
- custom JWT authorizers on the runtime and gateway
- allowlisted runtime headers
- Cedar-based policy enforcement on restricted tool calls
- runtime and gateway isolation through AWS-managed AgentCore infrastructure

The security boundary is not just a frontend check; the gateway policy engine enforces authorization at the tool-action boundary.

## Configuration and environment inputs

The app is configured with a few important runtime variables and external dependencies:

- `MEMORY_SHAREDMEMORY_ID` for memory session management
- `AWS_REGION` for service location and client configuration
- local deployment state files for runtime metadata
- SSM and Cognito lookups from the frontend for workshop setup and credentials

These inputs are expected to be available in the project environment when running the demo or deployed environment.

## Directory structure

```text
app/CustomerSupport/
├── main.py
├── README.md
├── frontend/
│   ├── frontend.py
│   ├── templates/
│   │   └── index.html
├── mcp_client/
│   └── client.py
├── memory/
│   └── session.py
├── model/
│   └── load.py
├── skills/
│   └── fetcher.py
├── tool/
│   ├── refund_schema.json
│   └── warranty_schema.json
├── images/
└── pyproject.toml
```

## Summary

The application is a full-stack customer support agent with a secure runtime, integrated memory, model-guided tool selection, gateway-protected actions, and a browser frontend. The behavior is implemented under the app code, while the root project defines the AgentCore services and policy deployment that power the runtime in AWS.

For the higher-level platform view, see [../../README.md](../../README.md). For the infrastructure configuration, see [../../agentcore/agentcore.json](../../agentcore/agentcore.json).
