"""Smoke tests — import checks, config loading, and mock display."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

def test_import_models():
    from multi_agent.models.task import Task, SubTask, TaskStatus, AgentType
    from multi_agent.models.agent_result import AgentResult
    assert TaskStatus.PENDING.value == "pending"
    assert AgentType.CODE.value == "code"


def test_import_config():
    from multi_agent.config import load_config, AppConfig
    assert AppConfig is not None


def test_import_platform_detect():
    from multi_agent.platform_detect import detect_platform, PLATFORM
    info = detect_platform()
    assert info.system in ("Darwin", "Linux", "Windows")


def test_import_audit_log():
    from multi_agent.audit_log import AuditLogger
    assert AuditLogger is not None


def test_import_gemini_client():
    from multi_agent.llm.gemini_client import GeminiClient, _strip_markdown_fences
    assert GeminiClient is not None


def test_import_display():
    from multi_agent.display.image_builder import build_progress_image, build_startup_image
    from multi_agent.display.display_manager import DisplayManager
    assert DisplayManager is not None


def test_import_agents():
    from multi_agent.agents.base_agent import BaseAgent
    from multi_agent.agents.code_agent import CodeAgent
    from multi_agent.agents.file_agent import FileAgent
    from multi_agent.agents.git_agent import GitAgent
    from multi_agent.agents.test_agent import TestAgent
    from multi_agent.agents.display_agent import DisplayAgent
    from multi_agent.agents.orchestrator_agent import OrchestratorAgent
    assert OrchestratorAgent is not None


def test_import_slack():
    from multi_agent.slack.message_builder import build_approval_message, build_ack_message
    from multi_agent.slack.approval_gate import ApprovalGate
    assert ApprovalGate is not None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def test_config_loads_from_yaml(tmp_path):
    from multi_agent.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "gemini:\n  model: gemini-test\nlog_level: INFO\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg.gemini.model == "gemini-test"
    assert cfg.log_level == "INFO"


def test_config_env_override(tmp_path, monkeypatch):
    from multi_agent.config import load_config

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("")
    cfg = load_config(str(cfg_file))

    assert cfg.gemini.api_key == "test-key-123"
    assert cfg.slack.bot_token == "xoxb-test"


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

def test_task_progress():
    from multi_agent.models.task import Task, SubTask, TaskStatus, AgentType

    task = Task(description="test task")
    assert task.progress_pct == 0

    st1 = SubTask(description="step1", agent_type=AgentType.CODE, status=TaskStatus.COMPLETED)
    st2 = SubTask(description="step2", agent_type=AgentType.FILE, status=TaskStatus.PENDING)
    task.subtasks = [st1, st2]
    assert task.progress_pct == 50


def test_agent_result_constructors():
    from multi_agent.models.agent_result import AgentResult

    ok = AgentResult.ok("hello", key="value")
    assert ok.success is True
    assert ok.output == "hello"
    assert ok.metadata["key"] == "value"

    fail = AgentResult.fail("oops")
    assert fail.success is False
    assert fail.error == "oops"


# ---------------------------------------------------------------------------
# Gemini strip fences
# ---------------------------------------------------------------------------

def test_strip_markdown_fences():
    from multi_agent.llm.gemini_client import _strip_markdown_fences

    raw = "```json\n{\"a\": 1}\n```"
    assert _strip_markdown_fences(raw) == '{"a": 1}'

    raw2 = "```\nhello\n```"
    assert _strip_markdown_fences(raw2) == "hello"

    raw3 = '{"b": 2}'
    assert _strip_markdown_fences(raw3) == '{"b": 2}'


# ---------------------------------------------------------------------------
# Display image builder
# ---------------------------------------------------------------------------

def test_build_progress_image():
    from multi_agent.display.image_builder import build_progress_image
    from PIL import Image

    img = build_progress_image(
        width=800,
        height=480,
        task_description="Write a hello world script",
        agent_name="code",
        step_description="Generating Python code",
        progress_pct=42,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (800, 480)


def test_build_startup_image():
    from multi_agent.display.image_builder import build_startup_image
    from PIL import Image

    img = build_startup_image(800, 480)
    assert isinstance(img, Image.Image)


# ---------------------------------------------------------------------------
# macOS display driver
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_macos_driver_saves_bmp(tmp_path):
    from multi_agent.display.macos_driver import MacOSDriver
    from multi_agent.display.image_builder import build_startup_image
    from PIL import Image
    import multi_agent.display.macos_driver as drv_module

    driver = MacOSDriver()
    await driver.init()

    img = build_startup_image(800, 480)
    output = tmp_path / "test_display.bmp"

    # Patch the output path
    original = drv_module._OUTPUT_PATH
    drv_module._OUTPUT_PATH = str(output)
    try:
        await driver.display_image(img)
        assert output.exists()
        loaded = Image.open(output)
        assert loaded.size == (800, 480)
    finally:
        drv_module._OUTPUT_PATH = original


# ---------------------------------------------------------------------------
# ApprovalGate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_gate_approve():
    from multi_agent.slack.approval_gate import ApprovalGate

    gate = ApprovalGate()

    async def resolve_soon():
        await asyncio.sleep(0.05)
        gate.resolve("test-id", approved=True)

    asyncio.create_task(resolve_soon())
    result = await gate.wait("test-id", timeout=2.0)
    assert result is True


@pytest.mark.asyncio
async def test_approval_gate_reject():
    from multi_agent.slack.approval_gate import ApprovalGate

    gate = ApprovalGate()

    async def resolve_soon():
        await asyncio.sleep(0.05)
        gate.resolve("test-id-2", approved=False)

    asyncio.create_task(resolve_soon())
    result = await gate.wait("test-id-2", timeout=2.0)
    assert result is False


@pytest.mark.asyncio
async def test_approval_gate_timeout():
    from multi_agent.slack.approval_gate import ApprovalGate

    gate = ApprovalGate()
    result = await gate.wait("no-one-resolves", timeout=0.1)
    assert result is False


# ---------------------------------------------------------------------------
# FileAgent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_file_agent_write_read(tmp_path):
    from multi_agent.agents.file_agent import FileAgent
    from multi_agent.models.task import SubTask, AgentType

    workspace = tmp_path / "workspace"
    backup = tmp_path / "backup"
    agent = FileAgent(str(workspace), str(backup))

    write_st = SubTask(
        description="Write hello",
        agent_type=AgentType.FILE,
        metadata={"operation": "write", "path": "hello.txt", "content": "Hello, World!"},
    )
    result = await agent.execute(write_st)
    assert result.success

    read_st = SubTask(
        description="Read hello",
        agent_type=AgentType.FILE,
        metadata={"operation": "read", "path": "hello.txt"},
    )
    result = await agent.execute(read_st)
    assert result.success
    assert result.output == "Hello, World!"


@pytest.mark.asyncio
async def test_file_agent_path_traversal(tmp_path):
    from multi_agent.agents.file_agent import FileAgent
    from multi_agent.models.task import SubTask, AgentType

    workspace = tmp_path / "workspace"
    backup = tmp_path / "backup"
    agent = FileAgent(str(workspace), str(backup))

    evil_st = SubTask(
        description="Path traversal attempt",
        agent_type=AgentType.FILE,
        metadata={"operation": "read", "path": "../../etc/passwd"},
    )
    result = await agent.execute(evil_st)
    assert not result.success
    assert "traversal" in result.error.lower()


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def test_build_approval_message():
    from multi_agent.slack.message_builder import build_approval_message
    from multi_agent.models.task import Task, SubTask, AgentType

    task = Task(description="deploy app")
    subtask = SubTask(description="git push origin main", agent_type=AgentType.GIT, requires_approval=True)

    blocks = build_approval_message(task, subtask)
    assert len(blocks) == 2
    # Check actions block has approve and reject buttons
    actions = blocks[1]
    assert actions["type"] == "actions"
    action_ids = [e["action_id"] for e in actions["elements"]]
    assert "approve_action" in action_ids
    assert "reject_action" in action_ids
