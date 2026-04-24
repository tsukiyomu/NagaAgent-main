# NagaAgent Game Module Deep Dive

This document explains how the `game/` package implements the multi‑agent, game‑theoretic planner used when `use_self_game=True` in the API layer.

## Purpose
- Generate specialist agents for a task, wire them into an interaction graph, and run a self‑game loop (actor → critic → checker) to raise output quality and novelty before the final answer is returned to the user.
- Provide reusable building blocks (role generation, routing, dispatch, self‑game engine) that can be tuned per domain via configuration.

## Architecture (paths)
- Entry point: `game/naga_game_system.py` (`NagaGameSystem`) orchestrates end‑to‑end flow and exposes a simple async API (`process_user_question`, `execute_self_game`, etc.).
- Data & config: `game/core/models/`
  - `data_models.py`: `Task`, `Agent`, `InteractionGraph`, `GameResult`, `GameSystemResult`, `SystemState`, `ThinkingVector`, etc.
  - `config.py`: `GameConfig` (Philoss/self‑game/interaction graph/system), plus domain presets via `get_domain_config`.
- Role & graph: `game/core/interaction_graph/`
  - `RoleGenerator`: full agent creation pipeline (calls `Distributor`, `PromptGenerator`).
  - `Distributor`: uses LLM to propose roles, assign responsibilities/skills/permissions.
  - `PromptGenerator`: builds per‑agent system prompts (skills, constraints, outputs).
  - `SignalRouter`: builds the interaction graph (allowed/forbidden paths, routing hops).
  - `DynamicDispatcher`: chooses the next agent to handle a message based on skills, load, and history.
  - `UserInteractionHandler`: mediates between user requests and the agent graph, packaging replies as `SystemResponse`.
- Self‑game: `game/core/self_game/`
  - `GameEngine`: coordinates Actor → Criticizer → PhilossChecker loops, tracks rounds/sessions.
  - `actor.py`: generates candidate outputs from agents.
  - `criticizer.py`: critiques/improves actor outputs.
  - `checker/philoss_checker.py`: scores novelty/quality via Philoss (configurable model).
- LLM adapter: `game/core/llm_adapter.py` wraps the OpenAI‑compatible client for internal calls.

## High‑level flow (happy path)
1) **Task intake** (`NagaGameSystem.process_user_question`)
   - Infer domain (heuristic or LLM), build `Task`, set iteration limits.
2) **Role generation** (`RoleGenerator.generate_agents`)
   - LLM proposes roles (`Distributor.generate_roles`), assigns collaboration permissions, creates system prompts, instantiates `Agent` dataclasses, and inserts a requester agent.
3) **Interaction graph** (`SignalRouter.build_interaction_graph`)
   - Produces allowed/forbidden paths and a collaboration matrix; respects `max_agents`, `max_routing_hops`, dynamic routing flag.
4) **Dynamic dispatch** (`DynamicDispatcher.dispatch_message`)
   - Selects next agent per message using skills/compatibility/workload/history.
5) **Self‑game loop** (`GameEngine.start_game_session`)
   - For each round: Actor generates outputs → Criticizer reviews/refines → PhilossChecker scores novelty/quality → decision to continue/complete/fail based on thresholds.
6) **User handoff** (`UserInteractionHandler.process_user_request`)
   - Aggregates current state, returns `SystemResponse` (content, timing, metadata).

## Configuration highlights (`game/core/models/config.py`)
- `PhilossConfig`: model name/path/device, token block size, prediction/novelty thresholds.
- `SelfGameConfig`: iterations, critics per round, timeouts, convergence/quality thresholds, thinking‑vector depth, max self routes.
- `InteractionGraphConfig`: agent count bounds, dynamic routing toggle, hop limits, template paths.
- `SystemConfig`: async on/off, max concurrent tasks, API rate limits, logging, checkpoint interval.
- `GameConfig`: bundles all and ensures required directories exist.

## Key data contracts (`game/core/models/data_models.py`)
- `Task`: id, description, domain, requirements, constraints, max_iterations.
- `Agent`: role metadata, system prompt, permissions, thinking vector, priority, id.
- `InteractionGraph`: agents + allowed/forbidden edges + collaboration matrix.
- `GameResult` / `GameSystemResult`: consolidated outcome, quality/novelty scores, phases completed, timing.
- `GameRound` / `GameSession` (in `game_engine.py`): per‑round outputs and session lifecycle.

## Integration points
- API layer (`apiserver/api_server.py`): when `use_self_game=True`, the request is routed through `NagaGameSystem` before responding; failures can fall back to normal chat.
- LLM backend: relies on the OpenAI‑compatible client (via `llm_adapter` or shared `naga_conversation`) for all role generation, prompting, actor/critic calls.
- Config: can be domain‑scoped (`get_domain_config`) to tune roles/iterations per scenario.

## Error handling & resilience
- Each stage logs progress; many steps are async with try/except wrapping (role generation, dispatch, self‑game rounds).
- PhilossChecker can be disabled or pointed to local weights; thresholds guard against low‑quality outputs.
- Dynamic routing and agent counts are capped by config to avoid blow‑ups.

## Practical usage tips
- Set `use_self_game=True` only for tasks that benefit from multi‑agent debate; otherwise it adds latency.
- Tune `SelfGameConfig.max_iterations` and `PhilossConfig` thresholds to balance quality vs speed.
- Limit agent counts (`InteractionGraphConfig.max_agents`) to keep prompts and routing manageable.
- Provide domain hints up front (or via `get_domain_config`) to improve role fidelity.

## Potential improvements
- Add caching for repeated role prompts per domain/task archetype.
- Plug in structured evaluation of critic outputs (e.g., rubric checks) before forwarding to checker.
- Expose telemetry (round times, Philoss scores) via an API for observability and auto‑tuning.
- Add guardrails to cap token budgets per round to avoid runaway costs.
