from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# Font paths to try in order
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_progress_image(
    width: int,
    height: int,
    task_description: str,
    agent_name: str,
    step_description: str,
    progress_pct: int,
    status_line: str = "",
) -> Image.Image:
    """
    Compose an 800×480 status image for the e-ink display.

    Layout:
      y=20  Title: "Multi-Agent Orchestrator"       font 28
      y=70  Task: <description[:60]>                font 22
      y=100 Agent: <agent_name>                     font 22
      y=130 Step: <step[:70]>                       font 20
      y=395 <pct>% progress label                   font 20
      y=420 [████░░░░░░░] progress bar
    """
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    font_title = _get_font(28)
    font_body = _get_font(22)
    font_step = _get_font(20)
    font_bar = _get_font(20)

    # Title
    draw.text((20, 20), "Multi-Agent Orchestrator", fill="black", font=font_title)

    # Horizontal rule under title
    draw.line([(20, 58), (width - 20, 58)], fill="black", width=2)

    # Task
    task_text = f"Task: {task_description[:60]}"
    draw.text((20, 70), task_text, fill="black", font=font_body)

    # Agent
    agent_text = f"Agent: {agent_name.upper()}"
    draw.text((20, 100), agent_text, fill="black", font=font_body)

    # Step
    step_text = f"Step: {step_description[:70]}"
    draw.text((20, 130), step_text, fill="black", font=font_step)

    # Optional status line
    if status_line:
        draw.text((20, 160), status_line[:80], fill="gray", font=font_step)

    # Progress percentage label
    pct_clamped = max(0, min(100, progress_pct))
    draw.text((20, 395), f"{pct_clamped}%", fill="black", font=font_bar)

    # Progress bar  (x=60..780, y=420, height=24)
    bar_x = 60
    bar_y = 420
    bar_width = width - 80
    bar_height = 24
    filled = int(bar_width * pct_clamped / 100)

    # Background (empty bar)
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], outline="black", fill="white")
    # Filled portion
    if filled > 0:
        draw.rectangle([bar_x, bar_y, bar_x + filled, bar_y + bar_height], fill="black")

    return img


def build_startup_image(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font = _get_font(32)
    font_sub = _get_font(20)
    draw.text((20, 200), "Multi-Agent Orchestrator", fill="black", font=font)
    draw.text((20, 250), "Starting up...", fill="gray", font=font_sub)
    return img


def build_idle_image(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font = _get_font(28)
    font_sub = _get_font(20)
    draw.text((20, 200), "Multi-Agent Orchestrator", fill="black", font=font)
    draw.text((20, 250), "Waiting for tasks...", fill="gray", font=font_sub)
    return img


def build_complete_image(width: int, height: int, task_description: str) -> Image.Image:
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font = _get_font(28)
    font_sub = _get_font(20)
    draw.text((20, 180), "Task Complete!", fill="black", font=font)
    draw.text((20, 230), task_description[:70], fill="black", font=font_sub)
    draw.text((20, 260), "100%", fill="black", font=font_sub)
    return img
