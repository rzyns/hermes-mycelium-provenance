from __future__ import annotations

from .provenance import ProvenanceState

__version__ = "0.1.0"
_STATE = ProvenanceState()


def register(ctx) -> None:
    """Register Hermes plugin hooks."""
    ctx.register_hook("on_session_start", _STATE.on_session_start)
    ctx.register_hook("pre_llm_call", _STATE.pre_llm_call)
    ctx.register_hook("pre_tool_call", _STATE.pre_tool_call)
    ctx.register_hook("post_tool_call", _STATE.post_tool_call)
    ctx.register_hook("post_llm_call", _STATE.post_llm_call)
    ctx.register_hook("on_session_finalize", _STATE.finalize)
    ctx.register_hook("on_session_reset", _STATE.finalize)
