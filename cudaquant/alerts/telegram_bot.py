"""Telegram interactive bot — long-polling listener with inline keyboards.

Handles:
- Incoming text messages → routes to READ-ONLY chat tool layer
- Inline keyboard button callbacks → two-step confirm for writes, one-tap for kill-switch
- Kill-switch DISENGAGE is NOT exposed here (UI-only)
"""

import asyncio
import json
import logging
import time

import httpx

from cudaquant.config.settings import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

POLL_TIMEOUT = 30  # seconds
POLL_INTERVAL = 2   # seconds between polls

# ── Budget (shared with in-app chat) ─────────────────────────────────────────

_tg_daily_calls = 0
_tg_daily_limit = 100
_tg_last_reset = time.time()


def _check_tg_budget() -> bool:
    global _tg_daily_calls, _tg_last_reset
    now = time.time()
    if now - _tg_last_reset > 86400:
        _tg_daily_calls = 0
        _tg_last_reset = now
    if _tg_daily_calls >= _tg_daily_limit:
        return False
    _tg_daily_calls += 1
    return True


# ── Polling loop ──────────────────────────────────────────────────────────────


async def run_telegram_polling():
    """Long-polling getUpdates loop. Runs as a background task."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN not configured — Telegram bot disabled")
        return

    base_url = f"https://api.telegram.org/bot{token}"
    offset = 0

    logger.info("Telegram bot polling started")

    while True:
        try:
            async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 10) as client:
                resp = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": POLL_TIMEOUT},
                )
                if resp.status_code != 200:
                    await asyncio.sleep(5)
                    continue

                data = resp.json()
                if not data.get("ok"):
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    if "message" in update:
                        await _handle_message(client, base_url, update["message"])
                    elif "callback_query" in update:
                        await _handle_callback(client, base_url, update["callback_query"])

        except Exception as e:
            logger.error("Telegram poll error: %s", e, exc_info=True)
            await asyncio.sleep(5)


# ── Message handling ─────────────────────────────────────────────────────────


async def _handle_message(client: httpx.AsyncClient, base_url: str, msg: dict):
    """Route incoming text messages to the READ-ONLY chat tool layer."""
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    if not chat_id or not text:
        return

    # Support @cudaquant mention
    text = text.replace("@cudaquant", "").strip()

    if not _check_tg_budget():
        await _send_message(client, base_url, chat_id, "⚠ Daily chat limit reached. Try again tomorrow.")
        return

    # Route to chat tool layer — read-only
    try:
        from cudaquant.llm.provider_factory import build_llm_provider

        provider = build_llm_provider()
        if not provider:
            await _send_message(client, base_url, chat_id, "LLM not configured — set LLM_API_KEY.")
            return

        # Simple: use the LLM directly with system prompt describing available tools
        from cudaquant.platform_tools.registry import READ_TOOLS

        tool_desc = "\n".join(f"- {name}: {fn.__doc__ or ''}" for name, fn in READ_TOOLS.items())

        system_prompt = (
            "You are CUDAQuant's Telegram assistant. You can discuss platform state and "
            "use these read-only tools:\n"
            f"{tool_desc}\n\n"
            f"Trading mode: {settings.TRADING_MODE}. Live: {settings.live_trading_enabled}.\n"
            "Be concise. If asked to execute actions, explain how via the UI."
        )

        # Call LLM and return response
        response_text = await _call_llm(system_prompt, text)
        await _send_message(client, base_url, chat_id, response_text[:4000])

    except Exception as e:
        logger.error("Telegram message handling error: %s", e)
        await _send_message(client, base_url, chat_id, "Sorry, something went wrong processing your message.")


async def _call_llm(system_prompt: str, user_text: str) -> str:
    """Call LLM and return response text."""
    from openai import OpenAI

    from cudaquant.config.settings import settings

    client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        max_tokens=500,
        temperature=0.3,
    )
    return resp.choices[0].message.content or "(no response)"


# ── Callback / button handling ────────────────────────────────────────────────


async def _handle_callback(client: httpx.AsyncClient, base_url: str, cb: dict):
    """Handle inline keyboard button presses."""
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    msg_id = cb.get("message", {}).get("message_id")
    data = cb.get("data", "")
    callback_id = cb.get("id", "")

    if not chat_id or not data:
        return

    # Acknowledge callback
    await client.post(f"{base_url}/answerCallbackQuery", json={"callback_query_id": callback_id})

    parts = data.split(":", 1)
    action = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    try:
        if action == "promote":
            await _handle_promote(client, base_url, chat_id, msg_id, arg)
        elif action == "promote_confirm":
            await _handle_promote_confirm(client, base_url, chat_id, msg_id, arg)
        elif action == "kill_engage":
            await _handle_kill_engage(client, base_url, chat_id, msg_id)
        elif action == "view_details":
            await _handle_view_details(client, base_url, chat_id, arg)
    except Exception as e:
        logger.error("Telegram callback error: %s", e)
        await _edit_message(client, base_url, chat_id, msg_id, f"❌ Failed: {e}")


async def _handle_promote(client, base_url, chat_id, msg_id, model_id):
    """First tap: show confirm/cancel."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Confirm", "callback_data": f"promote_confirm:{model_id}"},
            {"text": "❌ Cancel", "callback_data": "cancel"},
        ]]
    }
    await client.post(
        f"{base_url}/editMessageText",
        json={
            "chat_id": chat_id, "message_id": msg_id,
            "text": f"Promote model {model_id} to champion?",
            "reply_markup": keyboard,
        },
    )


async def _handle_promote_confirm(client, base_url, chat_id, msg_id, model_id):
    """Second tap: actually promote."""
    from cudaquant.ml.registry import get_shared_registry
    reg = get_shared_registry(settings.DUCKDB_PATH)
    m = reg.get(model_id)
    if not m:
        await _edit_message(client, base_url, chat_id, msg_id, f"❌ Model {model_id} not found")
        return

    if m.status.value == "candidate":
        ok = reg.promote_to_challenger(model_id)
    elif m.status.value == "challenger":
        ok = reg.promote_to_champion(model_id)
    else:
        await _edit_message(client, base_url, chat_id, msg_id, f"❌ Cannot promote from status: {m.status.value}")
        return

    await _edit_message(client, base_url, chat_id, msg_id,
                        f"✅ Promoted {model_id}" if ok else f"❌ Failed to promote {model_id}")


async def _handle_kill_engage(client, base_url, chat_id, msg_id):
    """One-tap kill switch engage."""
    from cudaquant.api.routes.risk_routes import _order_service
    _order_service.engage_kill_switch(reason="telegram")
    await _edit_message(client, base_url, chat_id, msg_id, "⚠ KILL SWITCH ENGAGED")


async def _handle_view_details(client, base_url, chat_id, model_id):
    """Show model details."""
    from cudaquant.ml.registry import get_shared_registry
    reg = get_shared_registry(settings.DUCKDB_PATH)
    m = reg.get(model_id)
    if not m:
        await _send_message(client, base_url, chat_id, f"Model {model_id} not found")
        return
    text = (
        f"Model: {m.model_id}\n"
        f"Family: {m.family}\n"
        f"Status: {m.status.value}\n"
        f"Metrics: {json.dumps(m.metrics, default=str)[:300]}\n"
        f"Created: {m.created_at}"
    )
    await _send_message(client, base_url, chat_id, text)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _send_message(client, base_url, chat_id, text, reply_markup=None):
    """Send a plain text message."""
    payload: dict = {"chat_id": chat_id, "text": text[:4096]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await client.post(f"{base_url}/sendMessage", json=payload)


async def _edit_message(client, base_url, chat_id, msg_id, text):
    """Edit an existing message."""
    await client.post(
        f"{base_url}/editMessageText",
        json={"chat_id": chat_id, "message_id": msg_id, "text": text[:4096]},
    )


# ── Public API for sending alerts ─────────────────────────────────────────────


async def send_telegram_alert(text: str, buttons: list[dict] | None = None):
    """Send an alert to the configured chat. Non-async-safe wrapper."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False

    payload: dict = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML"}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [buttons]}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error("Telegram alert send failed: %s", e)
        return False
