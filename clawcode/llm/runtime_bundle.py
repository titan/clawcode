"""Assemble coder provider, tools, system prompt, and agent extras in one place (CLI/TUI).

Avoids drift between TUI chat rebuild and non-interactive CLI paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..config.settings import Settings
from ..message import MessageService
from ..session import SessionService
from .base import BaseProvider
from .claw_support.config import claw_agent_kwargs_from_settings
from .claw_support.prompts import get_claw_mode_system_suffix
from .prompts import get_system_prompt, load_context_from_project
from .providers import create_provider, resolve_provider_from_model
from .tools import BaseTool, get_builtin_tools


def append_memory_snapshot_to_system_prompt(system_prompt: str) -> str:
    """Append memory/user snapshot blocks when available (fail-open)."""
    try:
        from ..claw_memory.memory_store import render_memory_prompt_blocks

        mem_block, user_block = render_memory_prompt_blocks()
        extras = [b.strip() for b in (mem_block, user_block) if isinstance(b, str) and b.strip()]
        if not extras:
            return system_prompt
        return (system_prompt.strip() + "\n\n" + "\n\n".join(extras)).strip()
    except Exception:
        return system_prompt


@dataclass
class CoderRuntimeBundle:
    """Everything needed to construct a coder :class:`~clawcode.llm.agent.Agent` or :class:`~clawcode.llm.claw.ClawAgent`."""

    settings: Settings
    provider: BaseProvider
    tools: list[BaseTool]
    system_prompt: str | None
    hook_engine: Any | None
    summarizer: Any | None
    claw_agent_kwargs: dict[str, Any]
    message_service: MessageService
    session_service: SessionService
    _lazy_summarizer: Any = None
    _lazy_summarizer_initialized: bool = False

    def _ensure_summarizer(self) -> Any:
        if self._lazy_summarizer_initialized:
            return self._lazy_summarizer
        self._lazy_summarizer_initialized = True
        try:
            from ..history.summarizer import SummarizerService

            self._lazy_summarizer = SummarizerService(
                settings=self.settings,
                message_service=self.message_service,
                session_service=self.session_service,
                provider=self.provider,
            )
        except Exception:
            self._lazy_summarizer = None
        return self._lazy_summarizer

    def make_claw_agent(self, *, permission_client: Any | None = None) -> Any:
        """Build a :class:`~clawcode.llm.claw.ClawAgent` (TUI coder path)."""
        from .claw import ClawAgent

        return ClawAgent(
            provider=self.provider,
            tools=self.tools,
            message_service=self.message_service,
            session_service=self.session_service,
            system_prompt=self.system_prompt,
            hook_engine=self.hook_engine,
            summarizer=self._ensure_summarizer(),
            settings=self.settings,
            permission_client=permission_client,
            **self.claw_agent_kwargs,
        )

    def make_plain_agent(self, *, permission_client: Any | None = None) -> Any:
        """Build a plain :class:`~clawcode.llm.agent.Agent` (e.g. CLI ``-p``)."""
        from .agent import Agent

        kw: dict[str, Any] = {
            "provider": self.provider,
            "tools": self.tools,
            "message_service": self.message_service,
            "session_service": self.session_service,
            "hook_engine": self.hook_engine,
            "settings": self.settings,
            "permission_client": permission_client,
            "summarizer": self._ensure_summarizer(),
        }
        if self.system_prompt is not None:
            kw["system_prompt"] = self.system_prompt
        return Agent(**kw)


def build_coder_runtime(
    *,
    settings: Settings,
    session_service: SessionService,
    message_service: MessageService,
    permissions: Any | None,
    plugin_manager: Any | None = None,
    lsp_manager: Any | None = None,
    for_claw_mode: bool | None = None,
    style: Literal["tui_coder", "cli_non_interactive"] = "tui_coder",
) -> CoderRuntimeBundle:
    """Create provider, tools, and prompt according to ``style``.

    Args:
        settings: Loaded application settings.
        session_service: Session persistence.
        message_service: Message persistence.
        permissions: Object with ``request()`` for TUI (e.g. app), or ``None`` for CLI auto-approve.
        plugin_manager: Optional plugin manager (hooks, skills text).
        lsp_manager: Optional LSP manager for diagnostics tool.
        for_claw_mode: Passed through to :func:`get_builtin_tools` (TUI desktop gating).
        style: ``tui_coder`` builds full system prompt + summarizer + claw kwargs;
            ``cli_non_interactive`` builds minimal stack (default Agent system prompt).
    """
    agent_config = settings.get_agent_config("coder")
    provider_name, provider_key = resolve_provider_from_model(
        agent_config.model,
        settings,
        agent_config,
    )
    provider_cfg = settings.providers.get(provider_key)
    api_key = getattr(provider_cfg, "api_key", None) if provider_cfg else None
    base_url = getattr(provider_cfg, "base_url", None) if provider_cfg else None

    provider = create_provider(
        provider_name=provider_name,
        model_id=agent_config.model,
        api_key=api_key,
        base_url=base_url,
    )

    tools = get_builtin_tools(
        permissions=permissions,
        session_service=session_service,
        message_service=message_service,
        lsp_manager=lsp_manager,
        plugin_manager=plugin_manager,
        for_claw_mode=for_claw_mode,
    )

    hook_engine = getattr(plugin_manager, "hook_engine", None) if plugin_manager else None

    if style == "cli_non_interactive":
        return CoderRuntimeBundle(
            settings=settings,
            provider=provider,
            tools=tools,
            system_prompt=None,
            hook_engine=hook_engine,
            summarizer=None,
            claw_agent_kwargs={},
            message_service=message_service,
            session_service=session_service,
        )

    # --- tui_coder ---
    wd = (getattr(settings, "working_directory", None) or "").strip()
    ctx_parts: list[str] = []
    if plugin_manager is not None and getattr(plugin_manager, "context_content", None):
        ctx_parts.append(str(plugin_manager.context_content))
    if wd:
        try:
            ctx_parts.append(
                load_context_from_project(wd, max_files=8, max_size=8000),
            )
        except Exception:
            pass
    merged_ctx = "\n\n".join(p for p in ctx_parts if p)
    system_prompt = get_system_prompt(
        agent_type="coder",
        context_paths_content=merged_ctx,
        skills_description=plugin_manager.get_skills_description() if plugin_manager else "",
        project_root=wd,
    ) + get_claw_mode_system_suffix()
    system_prompt = append_memory_snapshot_to_system_prompt(system_prompt)

    claw_agent_kwargs = claw_agent_kwargs_from_settings(settings)

    return CoderRuntimeBundle(
        settings=settings,
        provider=provider,
        tools=tools,
        system_prompt=system_prompt,
        hook_engine=hook_engine,
        summarizer=None,
        claw_agent_kwargs=claw_agent_kwargs,
        message_service=message_service,
        session_service=session_service,
    )


__all__ = [
    "CoderRuntimeBundle",
    "append_memory_snapshot_to_system_prompt",
    "build_coder_runtime",
]
