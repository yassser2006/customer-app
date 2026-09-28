# CustomerSupport

CustomerSupport is an Amazon Bedrock AgentCore customer support application designed for an e-commerce storefront. It combines a secure runtime, memory-backed conversational context, authenticated browser access, and policy-controlled tool execution to provide support for orders, product questions, and protected operational actions.

This repository is organized into two layers:

- the platform layer at the project root, which defines the AgentCore runtime, memory, gateway, policy engine, and deployment configuration
- the application layer under [app](app), which contains the actual Strands agent, tool set, frontend experience, and runtime integrations

## Purpose

The solution gives a support agent the ability to:

- answer general product and policy questions
- look up order status and product details
- retrieve customer information needed for support workflows
- handle refund scenarios through a controlled gateway-backed flow
- preserve memory across sessions so the support experience remains context-aware
- enforce policy-based authorization where refunds of $1,000 or less are allowed and larger refunds are denied
- protect sensitive actions from prompt-injection attempts that try to bypass authorization
- avoid duplicate refunds when the same action is retried
- surface failures through traces and telemetry so operational issues can be diagnosed and improved

## High-level architecture

![Architecture Diagram](image/architecture_diagram.png)

At a high level, the flow is:

1. A customer opens the web frontend.
2. The frontend authenticates using Cognito and obtains a JWT.
3. The browser calls the deployed AgentCore runtime with the token and session context.
4. The runtime loads the model, creates or reuses a memory-backed session, and decides which tools to use.
5. The agent may call local tools, memory-backed retrieval, MCP integrations, or AgentCore gateway actions protected by Cedar policies.
6. The result is streamed back to the user in the conversation UI.

## Proofs and validation walkthrough

The following screenshots capture representative validation scenarios for the chat experience and the policy-aware support flow.

### 1. Clean chat — agent response

![Clean chat](image/1-new-chat-s1.png)

This is an agent response proof: the support UI loads with an empty chat and the assistant is ready to engage in a new session.

The screenshot confirms the chat interface initializes correctly and that the conversation state starts clean before a user prompt is sent.

### 2. Greeting — agent response

![Greeting](image/2-Greeting-s1.png)

This is an agent response proof: the assistant responds naturally to a greeting and confirms it is ready to help with support requests.

The message demonstrates a standard conversational turn from the runtime and validates that the agent is live and responding coherently.

### 3. Checking an order — agent response

![Checking an order](image/3-checking-orders-s1.png)

This is an agent response proof: the customer asks about an order, and the assistant uses the order lookup tool to return the relevant status and purchase details.

The evidence shows the agent can answer a transactional query using its tool-backed workflow rather than relying on static text.

### 4. Asking about the customer name — agent response

![Name lookup](image/4-name-s1.png)

This is an agent response proof: the assistant does not yet know the customer name from memory, so the conversation proceeds normally after the user provides it.

The screenshot shows the distinction between a first-turn context and a memory-backed session, highlighting that the agent responds appropriately once the user supplies new context.

### 5. Memory working across sessions — agent response

![Memory across sessions](image/5-Memory-s2.png)

This is an agent response proof: a new session still recalls prior customer information and answers using remembered context.

The evidence confirms that memory persistence is working between separate conversations and that the assistant can personalize follow-up responses.

### 6. Refund under $1,000 — gateway/policy proof

![Refund under $1,000](image/6-refund-under-1000-s2-p1.png)

This is a gateway/policy proof: the customer requests a refund below the policy threshold, and the request proceeds through the authorized workflow.

The screenshot shows the approved refund path and confirms the runtime is not blocking valid low-value refund requests.

### 7. Refund under $1,000 continuation — gateway/policy proof

![Refund continuation](image/7-refund-under-1000-s2-p2.png)

This is a gateway/policy proof: the same valid refund request continues to completion without violating the policy boundary.

The image demonstrates the authorized path remains consistent through the end of the workflow and shows the permitted refund flow is being enforced as intended.

### 8. Refunding a previously refunded order — backend evidence

![Duplicate refund attempt](image/8-refund-under-1000-s2-duplicated.png)

This is backend evidence: the system detects that the order was already refunded and prevents a duplicate refund instead of creating a second one.

The screenshot demonstrates idempotency and duplicate-protection behavior in the refund backend rather than just a conversational response.

### 9. Refunding a canceled order — backend evidence

![Canceled order refund](image/9-refund-under-1000-s2-cancelled.png)

This is backend evidence: the refund backend recognizes that the order is canceled and blocks the refund flow because the request is invalid for that order state.

The image shows the business rule is enforced at the operational layer and not just suggested by the assistant response.

### 10. Refund above $1,000 — gateway/policy proof

![Refund above threshold denied](image/10-refund-above-1000-s3-refused.png)

This is a gateway/policy proof: the request exceeds the allowed limit, so the agent is denied and the policy guardrail is enforced.

The denial case confirms the authorization boundary is active and that larger refund amounts are rejected at the policy layer.

These screenshots together distinguish between agent behavior, runtime policy enforcement, and backend business-logic validation so the evidence is clearer to reviewers.

### Additional validation screenshots

#### Prompt injection attempt — gateway/policy proof

![Prompt injection attempt](image/11-prompt-injection.png)

This is a gateway/policy proof: the system resists a prompt-injection attempt and keeps the assistant inside the allowed support workflow.

#### Refund exact $1,000 continuation — gateway/policy proof

![Refund exact $1,000 continuation](image/12-%20refund-exact-1000-p1.png)

This is a gateway/policy proof: the boundary case at exactly $1,000 is allowed and remains within the permitted refund limit.

#### Refund exact $1,000 completion — backend evidence

![Refund exact $1,000 completion](image/13-%20refund-exact-1000-p2.png)

This is backend evidence: the exact-threshold refund completes successfully without triggering a policy denial, confirming the edge case is handled correctly.

#### Refund over $1,000 part 1 — gateway/policy proof

![Refund over $1,000 part 1](image/14-%20refund-exact-1001-p1.png)

This is a gateway/policy proof: the conversation begins with a refund request above the threshold, which triggers the authorization check before the flow proceeds.

#### Refund over $1,000 part 2 — gateway/policy proof

![Refund over $1,000 part 2](image/15-%20refund-exact-1001-p2.png)

This is a gateway/policy proof: the denial path is enforced when the requested refund exceeds the maximum allowed amount.

#### Evaluation metrics — backend evidence

![Evaluation metrics](image/16-Evaluation-metrics.png)

This is backend evidence: the evaluation summary shows the measured quality, safety, and policy-compliance checks used to validate the assistant.

#### Different memory states — agent response

![Different memory states](image/17-Different-memory.png)

This is an agent response proof: the assistant’s memory context differs across conversations, showing how personalized support remains consistent while the state stays scoped by user and session.

## Major components

### AgentCore platform

The root project configures the deployment and runtime surface in:

- [agentcore/agentcore.json](agentcore/agentcore.json)
- [agentcore/aws-targets.json](agentcore/aws-targets.json)
- [agentcore/cdk](agentcore/cdk)

This layer defines the runtime, memory, gateway, authorizer, policy engine, and deployment targets that make the app live in AWS.

### Application runtime

The application logic lives under [app/CustomerSupport](app/CustomerSupport) and includes:

- the Strands agent entrypoint
- the built-in support tools
- MCP client integrations
- memory session handling
- the frontend user interface
- model configuration and runtime orchestration

### Security and authorization

The solution uses AWS-managed authentication and policy enforcement so that sensitive operations are not exposed without checks. The runtime accepts authenticated requests, while gateway-backed actions such as refund and warranty processing are gated by policy rules before execution. In the support workflow, the agent checks order status, reads customer context, and invokes refund actions only when the authorization policy allows them; refunds at or below $1,000 are permitted, while larger amounts are denied. The design also accounts for prompt-injection attempts, retry behavior, and post-incident troubleshooting through traces and telemetry, with failure scenarios used to validate the system’s resilience.

## Deployment and setup

The project is deployed through the AgentCore CLI rather than a separate hand-managed runtime template. The main workflow is:

```bash
agentcore validate
agentcore deploy
agentcore status
```

For local iteration and smoke testing:

```bash
cd app/CustomerSupport
agentcore dev
agentcore invoke --dev "What can you do?"
```

## How the pieces fit together

- The runtime and AWS resources are defined at the project root.
- The app code implements the actual customer service behavior.
- Memory provides continuity across sessions and user context.
- The gateway exposes protected operations behind policy checks.
- The frontend is a thin client layered on top of the deployed runtime.

This separation keeps the infrastructure concerns in the root project and the behavioral logic in the app directory.

## More detail

For the complete application-level reference, including agent behavior, tools, memory configuration, gateway policy details, and frontend flow, see [app/README.md](app/README.md).
