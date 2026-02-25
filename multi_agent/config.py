from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SlackConfig:
    bot_token: str = ""
    app_token: str = ""
    channel_id: str = ""
    approval_timeout_seconds: int = 300


@dataclass
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 8192


@dataclass
class DisplayConfig:
    epd_model: str = "epd7in5_V2"
    width: int = 800
    height: int = 480


@dataclass
class WorkspaceConfig:
    path: str = "./workspace"
    backup_path: str = "./backups"


@dataclass
class AppConfig:
    slack: SlackConfig = field(default_factory=SlackConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    log_path: str = "./logs/audit.jsonl"
    log_level: str = "DEBUG"


def load_config(config_path: str = "config.yaml") -> AppConfig:
    raw: dict = {}
    if Path(config_path).exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}

    slack_raw = raw.get("slack", {})
    gemini_raw = raw.get("gemini", {})
    display_raw = raw.get("display", {})
    workspace_raw = raw.get("workspace", {})

    slack = SlackConfig(
        bot_token=os.environ.get("SLACK_BOT_TOKEN") or slack_raw.get("bot_token", ""),
        app_token=os.environ.get("SLACK_APP_TOKEN") or slack_raw.get("app_token", ""),
        channel_id=os.environ.get("SLACK_CHANNEL_ID") or slack_raw.get("channel_id", ""),
        approval_timeout_seconds=slack_raw.get("approval_timeout_seconds", 300),
    )

    gemini = GeminiConfig(
        api_key=os.environ.get("GEMINI_API_KEY") or gemini_raw.get("api_key", ""),
        model=gemini_raw.get("model", "gemini-2.0-flash"),
        temperature=gemini_raw.get("temperature", 0.7),
        max_tokens=gemini_raw.get("max_tokens", 8192),
    )

    display = DisplayConfig(
        epd_model=display_raw.get("epd_model", "epd7in5_V2"),
        width=display_raw.get("width", 800),
        height=display_raw.get("height", 480),
    )

    workspace = WorkspaceConfig(
        path=workspace_raw.get("path", "./workspace"),
        backup_path=workspace_raw.get("backup_path", "./backups"),
    )

    return AppConfig(
        slack=slack,
        gemini=gemini,
        display=display,
        workspace=workspace,
        log_path=raw.get("log_path", "./logs/audit.jsonl"),
        log_level=raw.get("log_level", "DEBUG"),
    )
