# NagaAgent Gateway Security Review and Remediation Plan

## 1. Review Scope

This document records a static review of the NagaAgent architecture and selected gateway, authentication, tool, WebSocket, configuration, and upload implementations. It compares the current design with a typical production deployment using Spring Cloud Gateway and Spring Security.

This is an architecture and source-code assessment, not a penetration test.

## 2. Overall Finding

The current implementation is not sufficiently secure for:

- Internet-facing deployment.
- Exposure to a local network.
- Multi-user or multi-tenant operation.
- Processing valuable credentials or sensitive conversations without additional controls.

It may eventually be suitable for a single-user desktop deployment, but only after all privileged services are restricted to loopback access and protected by a local authentication mechanism.

A bare Spring Cloud Gateway is not automatically secure. However, a properly configured Spring Cloud Gateway with Spring Security provides a substantially stronger security boundary than the current NagaAgent implementation.

## 3. Security Findings

### 3.1 Critical: Credentials and Tokens Use Plain HTTP

`BUSINESS_URL` uses a hard-coded `http://` address:

- [`apiserver/naga_auth.py`](../apiserver/naga_auth.py)

The authentication flow sends the following over this connection:

- Username and password during login.
- Access tokens in `Authorization` headers.
- Refresh tokens in cookies.
- Model requests and potentially sensitive conversation content.

This permits interception or modification by an attacker capable of observing or altering network traffic.

### 3.2 Critical: Internal Control Services Bind to All Interfaces

The Agent and MCP servers are started on `0.0.0.0`:

- [`main.py`](../main.py)

These services expose powerful operations, including:

- MCP tool scheduling and execution.
- OpenClaw configuration and messaging.
- Agent creation, modification, and deletion.
- Skill and MCP installation.
- Runtime and gateway control.
- Travel, proactive-vision, heartbeat, and DogTag operations.

The reviewed route groups do not have a consistent authentication or authorization layer. Any device that can reach the ports may be able to invoke privileged behavior.

### 3.3 Critical: Authentication Is Global State, Not Per-Request Identity

The API middleware reads any bearer value and stores it in module-level authentication state:

- [`apiserver/api_server.py`](../apiserver/api_server.py)
- [`apiserver/naga_auth.py`](../apiserver/naga_auth.py)

The middleware does not validate the token signature, issuer, audience, expiry, or scopes before replacing the global token.

Consequences include:

- One request can change the identity used by later requests.
- Concurrent users can overwrite one another's token.
- An arbitrary bearer string can temporarily make the process appear authenticated.
- Authorization decisions cannot reliably use a request-scoped principal.

### 3.4 Critical: Configuration and Secrets Are Exposed

`GET /system/config` returns a complete configuration snapshot, while `POST /system/config` modifies it:

- [`apiserver/routes/system.py`](../apiserver/routes/system.py)
- [`system/config_manager.py`](../system/config_manager.py)

The configuration model can contain:

- Model API keys.
- Neo4j credentials.
- MQTT credentials.
- TTS, voice, embedding, and computer-control API keys.
- Memory tokens and service addresses.

These endpoints are not protected by a clear administrator authorization policy, and sensitive values are not redacted before being returned.

### 3.5 High: Session Ownership Is Not Enforced

Session endpoints allow callers to:

- List all sessions.
- Read any session by ID.
- Delete any session.
- Clear all sessions.

See:

- [`apiserver/routes/session.py`](../apiserver/routes/session.py)

The routes do not associate resources with a request-scoped user or verify ownership. This is unacceptable for multi-user deployment.

### 3.6 High: Unsafe File Upload Handling

The document upload endpoint joins the upload directory with the client-provided filename and writes it directly:

- [`apiserver/routes/extensions.py`](../apiserver/routes/extensions.py)

Missing controls include:

- Canonical-path containment verification.
- Generated server-side filenames.
- File-size limits.
- Safe overwrite policy.
- Strong content validation.
- Per-user storage separation.

This creates path-traversal, file-overwrite, disk-exhaustion, and parser-abuse risks.

### 3.7 High: WebSocket Authentication and Authorization Are Missing

The WebSocket endpoint accepts a caller-provided `session_id` and immediately registers the connection:

- [`apiserver/routes/tools.py`](../apiserver/routes/tools.py)
- [`apiserver/websocket_manager.py`](../apiserver/websocket_manager.py)

The broadcast endpoint is also not protected by a clear internal-service authorization policy.

Risks include:

- Subscribing to another session.
- Receiving private notifications.
- Injecting misleading broadcast messages.
- Cross-origin WebSocket abuse.

### 3.8 High: Tool Execution Has an Excessive Trust Boundary

The MCP server exposes `/schedule` and `/call` without a consistent authentication layer:

- [`mcpserver/mcp_server.py`](../mcpserver/mcp_server.py)

Because tools can interact with files, browsers, the screen, external services, and other local processes, unauthorized MCP access can have a much larger effect than an ordinary API data leak.

### 3.9 High: Arbitrary Callback URLs Create SSRF Risk

The MCP scheduling request accepts a caller-controlled `callback_url`, and the server sends HTTP requests to it:

- [`mcpserver/mcp_server.py`](../mcpserver/mcp_server.py)

There is no visible scheme, hostname, IP-range, redirect, or destination allowlist. This creates a server-side request forgery risk against localhost, private networks, and other reachable services.

### 3.10 Medium: CORS Is Overly Permissive

The API, Agent, and MCP services use wildcard origins, methods, and headers:

- [`apiserver/api_server.py`](../apiserver/api_server.py)
- [`agentserver/agent_server.py`](../agentserver/agent_server.py)
- [`mcpserver/mcp_server.py`](../mcpserver/mcp_server.py)

This configuration is inappropriate for privileged local services and makes browser-to-local-service attacks easier.

### 3.11 Medium: Resource-Abuse Controls Are Missing

No consistent gateway-level controls were identified for:

- Request rate limits.
- Per-user quotas.
- Concurrent LLM or tool-call limits.
- Upload and request-body limits.
- WebSocket connection limits.
- SSE connection limits.
- Global time budgets.
- Circuit breakers and bulkheads.

This is especially important because `/chat/stream` is a thick gateway path capable of triggering expensive LLM and tool operations.

### 3.12 Medium: Refresh Tokens Are Stored in Plaintext

The refresh token is written to a local `.auth_session` JSON file:

- [`apiserver/naga_auth.py`](../apiserver/naga_auth.py)

For a desktop application, long-lived tokens should preferably be stored using an operating-system credential facility such as Windows Credential Manager/DPAPI, macOS Keychain, or a Linux secret service.

## 4. Architectural Comparison

### 4.1 Current NagaAgent Design

The architecture describes the API server as a unified entry layer, but the frontend also connects directly to the Agent and Voice services:

- [`docs/architecture/NagaAgent_architecturev2.md`](architecture/NagaAgent_architecturev2.md)

This means the API server is not a complete security choke point.

The API server is also a thick gateway. It performs or initiates:

- Session lifecycle management.
- Context assembly.
- LLM requests.
- SSE streaming.
- Tool dispatch.
- Persistence.
- Configuration operations.
- Internal proxy operations.

Combining edge routing and privileged business execution increases attack surface and blast radius.

### 4.2 Typical Secured Spring Cloud Gateway Design

A production Spring Cloud Gateway deployment commonly places one externally reachable gateway in front of private downstream services.

Typical controls include:

| Control | Secured Spring Cloud Gateway | Current NagaAgent |
|---|---|---|
| Request authentication | JWT or opaque-token validation for every protected request | Bearer value copied into global state |
| Request identity | Request-scoped `Principal` and security context | Module-level shared access token |
| Route authorization | Roles, authorities, scopes, and route policies | No consistent endpoint authorization matrix |
| Downstream identity | Controlled token relay or service credentials | Mostly unauthenticated internal HTTP |
| Network boundary | Gateway is public; downstream services are private | Agent and MCP bind to all interfaces |
| Session isolation | Resource ownership checked against the principal | Global session access by session ID |
| Rate limiting | Principal/IP/client-based rate-limiter filters | No consistent gateway rate limit |
| Resilience | Timeouts, circuit breakers, retries, and bulkheads | Partial local timeouts and retries |
| Security headers | Central secure-header policy | No comparable global policy identified |
| WebSocket security | Authenticated handshake and principal-based authorization | Session ID accepted without authentication |
| Secret handling | External secret store or protected environment configuration | Complete configuration can be returned by an API |

Relevant official Spring documentation:

- [Spring Security OAuth2 Resource Server JWT](https://docs.spring.io/spring-security/reference/reactive/oauth2/resource-server/jwt.html)
- [Spring Cloud Gateway TokenRelay](https://docs.spring.io/spring-cloud-gateway/reference/spring-cloud-gateway-server-webflux/gatewayfilter-factories/tokenrelay-factory.html)
- [Spring Cloud Gateway RequestRateLimiter](https://docs.spring.io/spring-cloud-gateway/reference/spring-cloud-gateway-server-webflux/gatewayfilter-factories/requestratelimiter-factory.html)
- [Spring Cloud Gateway SecureHeaders](https://docs.spring.io/spring-cloud-gateway/reference/spring-cloud-gateway-server-webflux/gatewayfilter-factories/secureheaders-factory.html)
- [Spring Security WebSocket Security](https://docs.spring.io/spring-security/reference/servlet/integrations/websocket.html)

### 4.3 Recommended Target Architecture

```text
Electron / Web / PyQt Client
            |
            v
Single API Gateway or Desktop BFF
  - TLS or loopback-only transport
  - per-request authentication
  - authorization and ownership checks
  - CORS and WebSocket origin policy
  - rate, size, concurrency, and time limits
  - audit and correlation IDs
            |
            v
Private Internal Services
  - Agent
  - MCP / Tool Runner
  - Voice
  - OpenClaw
  - Memory
  - LLM Adapter

Internal services accept only authenticated service-to-service calls and are not directly reachable from untrusted clients.
```

The agentic loop, tool execution, persistence, and administrative operations should live behind the gateway rather than inside the public edge boundary.

## 5. Prioritized Remediation Plan

### Phase 0: Immediate Exposure Reduction

1. Replace all authentication and model-service `http://` URLs with verified HTTPS endpoints.
2. Bind Agent, MCP, Voice, and OpenClaw services to `127.0.0.1` by default.
3. Remove the automatic fallback from loopback binding to `0.0.0.0`.
4. Add operating-system firewall rules or deployment network policies that block direct access to internal ports.
5. Disable or protect API documentation outside development.
6. Treat any existing credentials transmitted over plain HTTP as compromised and rotate them after HTTPS is deployed.

### Phase 1: Establish a Real Identity Boundary

1. Validate every protected bearer token using one of:
   - JWT signature, issuer, audience, expiry, and scope validation.
   - Opaque-token introspection against the authorization service.
2. Store the authenticated identity in request-local context.
3. Remove module-level mutable authentication as the source of request identity.
4. Define a default-deny endpoint authorization policy.
5. Create explicit roles or scopes, such as:
   - `chat:use`
   - `session:read`
   - `session:delete`
   - `tool:invoke`
   - `config:read`
   - `config:write`
   - `admin:runtime`
6. Give internal services separate service identities or use mTLS.

### Phase 2: Protect Resources and Privileged Operations

1. Associate sessions, travel tasks, memory, WebSockets, and agents with an owner identity.
2. Enforce ownership on every read, update, delete, stream, and subscription operation.
3. Restrict configuration, skill installation, MCP installation, OpenClaw control, broadcasting, and tool invocation to authorized roles.
4. Redact all secret fields from configuration responses.
5. Store secrets outside ordinary configuration snapshots.
6. Replace plaintext refresh-token files with operating-system protected credential storage.

### Phase 3: Harden Input and Egress Handling

1. Generate server-side upload names.
2. Resolve and verify that every upload path remains inside its assigned directory.
3. Add file-size, request-body, decompression, and parser limits.
4. Validate actual content rather than relying only on extensions.
5. Restrict callback URLs to approved HTTPS origins.
6. Resolve callback hostnames and reject loopback, link-local, multicast, private, and metadata-service destinations unless explicitly required.
7. Revalidate every redirect destination.
8. Add outbound network allowlists for tools where practical.

### Phase 4: Browser, SSE, and WebSocket Security

1. Replace wildcard CORS with an explicit origin allowlist.
2. Allow only required methods and headers.
3. Validate `Origin` during WebSocket handshakes.
4. Authenticate WebSocket connections.
5. Check session ownership before registering a socket.
6. Protect broadcast operations with an internal-service role.
7. Add SSE and WebSocket connection, duration, and message-size limits.

### Phase 5: Resource Governance and Resilience

1. Add per-principal and per-IP rate limits.
2. Add separate cost limits for:
   - Login and verification.
   - Chat and LLM requests.
   - Tool execution.
   - Uploads.
   - Travel and browser automation.
3. Add concurrency limits and queues for expensive operations.
4. Apply request, stream, tool, and total workflow deadlines.
5. Add circuit breakers and bounded retries.
6. Prevent retries for non-idempotent actions unless idempotency is implemented.

### Phase 6: Verification and Security Gates

Add automated tests for:

- Missing, malformed, expired, wrong-issuer, and wrong-audience tokens.
- Role and scope enforcement for every privileged route.
- Cross-user session access.
- Cross-session WebSocket subscription.
- Unauthenticated broadcast and tool execution.
- File path traversal and overwrite attempts.
- Oversized and malformed file uploads.
- SSRF to loopback, private networks, redirects, and metadata addresses.
- CORS and WebSocket origin rejection.
- Rate-limit, concurrency-limit, and timeout behavior.
- Secret redaction.
- Concurrent requests using different user identities.

Security tests should become blocking CI gates for authentication, authorization, file handling, SSRF, and internal-service exposure.

## 6. Acceptance Criteria

The system should not be considered ready for networked production until:

- No credentials or bearer tokens are transmitted over plain HTTP.
- Only the intended gateway is reachable from untrusted networks.
- Every protected request receives a validated, request-scoped identity.
- Every privileged route has an explicit authorization rule.
- All user-owned resources enforce ownership.
- Internal service calls are authenticated.
- Configuration responses cannot disclose secrets.
- Upload traversal and arbitrary callback destinations are blocked.
- WebSocket and SSE channels enforce authentication and resource ownership.
- Rate, size, concurrency, and time limits are tested.
- Security regression tests pass in CI.

