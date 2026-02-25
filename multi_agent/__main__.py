"""
Multi-Agent Task Orchestrator — asyncio entry point.

Usage:
    poetry run multi-agent
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from multi_agent.audit_log import AuditLogger
from multi_agent.config import load_config
from multi_agent.display.display_manager import DisplayManager
from multi_agent.agents.display_agent import DisplayAgent
from multi_agent.agents.orchestrator_agent import OrchestratorAgent
from multi_agent.llm.gemini_client import GeminiClient
from multi_agent.slack.approval_gate import ApprovalGate
from multi_agent.slack.bot import SlackBot


def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.DEBUG)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def main() -> None:
    config = load_config("config.yaml")
    _setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Multi-Agent Orchestrator starting up...")

    # Ensure directories exist
    Path(config.workspace.path).mkdir(parents=True, exist_ok=True)
    Path(config.workspace.backup_path).mkdir(parents=True, exist_ok=True)
    Path(config.log_path).parent.mkdir(parents=True, exist_ok=True)

    # Core singletons
    audit = AuditLogger(config.log_path)
    await audit.setup()

    display_mgr = DisplayManager(
        width=config.display.width,
        height=config.display.height,
    )
    await display_mgr.init()

    display_agent = DisplayAgent(display_mgr)
    await display_agent.show_startup()

    gemini = GeminiClient(
        api_key=config.gemini.api_key,
        model=config.gemini.model,
        temperature=config.gemini.temperature,
        max_tokens=config.gemini.max_tokens,
    )

    approval_gate = ApprovalGate()

    def orchestrator_factory(slack_post_fn=None) -> OrchestratorAgent:
        return OrchestratorAgent(
            gemini=gemini,
            display_agent=display_agent,
            audit_logger=audit,
            workspace_path=config.workspace.path,
            backup_path=config.workspace.backup_path,
            approval_gate=approval_gate,
            slack_post_fn=slack_post_fn,
        )

    # Check if Slack is configured
    if not config.slack.bot_token or not config.slack.app_token:
        logger.warning(
            "Slack tokens not configured. Running in display-only mode. "
            "Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env to enable the bot."
        )
        await display_agent.show_idle()
        logger.info("Press Ctrl+C to exit.")
        try:
            await asyncio.Event().wait()  # Wait forever
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        return

    bot = SlackBot(
        config=config,
        audit_logger=audit,
        approval_gate=approval_gate,
        orchestrator_factory=orchestrator_factory,
    )

    await display_agent.show_idle()
    logger.info("Slack bot starting...")

    # Graceful shutdown
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _on_signal():
        logger.info("Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal)

    try:
        bot_task = asyncio.create_task(bot.start())
        await stop_event.wait()
        bot_task.cancel()
        try:
            await bot_task
        except (asyncio.CancelledError, Exception):
            pass
    finally:
        await bot.stop()
        await display_mgr.shutdown()
        logger.info("Multi-Agent Orchestrator stopped.")


def run() -> None:
    """Entry point for `poetry run multi-agent`."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
