"""Chat API route — LLM-powered conversation with read-only platform tools."""
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from cudaquant.api.auth import require_auth
from cudaquant.config.settings import settings
from cudaquant.llm.provider_factory import build_llm_provider
from cudaquant.platform_tools.registry import READ_TOOLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(require_auth)])

# Separate budget from LLMResearchAgent's autonomous budget
_chat_daily_calls = 0
_chat_daily_limit = 100
_chat_last_reset = time.time()


def _check_chat_budget() -> tuple[bool, str]:
    global _chat_daily_calls, _chat_last_reset
    now = time.time()
    if now - _chat_last_reset > 86400:
        _chat_daily_calls = 0
        _chat_last_reset = now
    if _chat_daily_calls >= _chat_daily_limit:
        return False, f"chat daily limit reached ({_chat_daily_limit} calls)"
    _chat_daily_calls += 1
    return True, "ok"


SYSTEM_PROMPT = """You are CUDAQuant's platform assistant — a quant trading research system running on an NVIDIA Jetson Orin Nano.

Your capabilities (read-only):
- list_strategies() — see available trading strategies and their parameters
- list_experiments(status, origin) — see experiment history
- get_experiment(id) — get experiment details
- list_models(status) — see model registry with champion/challenger status
- get_model(id) — get model details including metrics
- get_model_live_performance(id) — see realized vs backtest metrics
- run_backtest_result(strategy, params, symbol, days) — run a backtest
- get_regime_state(symbol) — current market regime classification
- get_scheduler_status() — see scheduled job status
- get_dispatch_stats() — GPU vs CPU feature computation counts
- get_account() — account cash, portfolio value, buying power
- get_positions() — current open positions
- get_order_history(limit) — recent order history

You CANNOT execute actions. If asked to promote a model, place an order, or change settings, explain how to do it via the UI — you don't have those tools.

Be concise. When citing data, mention the specific values. Always prefer tools over generic knowledge — if a question can be answered by calling a tool, call it first.

Current platform state:
- Trading mode: {trading_mode}
- Live trading: {live_enabled}
- GPU active: {gpu_active}
- ML GPU active: {ml_gpu_active}
"""


def _build_system_prompt() -> str:
    gpu = {"gpu_active": False, "ml_gpu_active": False}
    try:
        from cudaquant.features.gpu.bindings import gpu_available
        gpu["gpu_active"] = gpu_available()
    except Exception:
        pass
    try:
        from cudaquant.ml.gpu_models import _gpu_ml_available
        gpu["ml_gpu_active"] = _gpu_ml_available()
    except Exception:
        pass

    from cudaquant.execution.trading_mode import get_shared_trading_mode
    tm = get_shared_trading_mode(settings.DUCKDB_PATH).get_state()

    return SYSTEM_PROMPT.format(
        trading_mode=tm["effective_mode"],
        live_enabled=tm["effective_mode"] == "live",
        gpu_active=gpu["gpu_active"],
        ml_gpu_active=gpu["ml_gpu_active"],
    )


@router.post("/")
async def chat(payload: dict):
    """Chat with the platform assistant. Uses read-only tools.

    Payload: {"messages": [{"role": "user", "content": "..."}, ...]}
    """
    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(400, "messages array required")

    ok, reason = _check_chat_budget()
    if not ok:
        raise HTTPException(429, reason)

    provider = build_llm_provider()
    if not provider:
        raise HTTPException(503, "LLM not configured — set LLM_API_KEY")

    # Build conversation with system prompt
    system_msg = {"role": "system", "content": _build_system_prompt()}
    conversation = [system_msg] + messages

    # Call LLM with tool definitions
    tool_defs = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": fn.__doc__ or f"Call {name}",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
            }
        }
        for name, fn in READ_TOOLS.items()
    ]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)

        # Simple: one LLM call — if it requests tools, call them and return the data
        # For a proper tool-calling loop, we'd need multi-turn — this is sufficient for v1
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=conversation,
            tools=tool_defs,
            max_tokens=800,
            temperature=0.3,
        )

        choice = response.choices[0]
        content = choice.message.content or ""

        # If the LLM requested tool calls, execute them and send results back
        if choice.message.tool_calls:
            tool_results = []
            # Add the assistant's tool-call request to the conversation
            conversation.append({
                "role": "assistant",
                "content": choice.message.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in choice.message.tool_calls
                ],
            })
            # Execute tools
            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                fn = READ_TOOLS.get(fn_name)
                result_str = json.dumps({"error": f"unknown tool: {fn_name}"})
                if fn:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        result_str = json.dumps(fn(**args), default=str)
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)})
                tool_results.append({"tool": fn_name, "result": json.loads(result_str)})
                # Add tool result to conversation
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

            # Second LLM call — synthesize response from tool results
            response2 = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=conversation,
                max_tokens=800,
                temperature=0.3,
            )
            content = response2.choices[0].message.content or ""
        else:
            content = choice.message.content or ""
            tool_results = []

        return {
            "content": content,
            "tool_calls": tool_results,
            "budget_remaining": _chat_daily_limit - _chat_daily_calls,
        }

    except Exception as e:
        logger.error("Chat failed: %s", e)
        raise HTTPException(500, f"LLM call failed: {e}") from e
