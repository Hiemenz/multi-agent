"""RPi hardware e-ink driver — Linux only."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PIL import Image

logger = logging.getLogger(__name__)


class EinkDriver:
    """Wraps the Waveshare EPD7in5 V2 hardware driver."""

    def __init__(self) -> None:
        # Import lazily so macOS doesn't blow up on missing RPi libs
        from multi_agent.display.waveshare_epd import epd7in5_V2
        self._epd_module = epd7in5_V2
        self._epd = None

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        self._epd = self._epd_module.EPD()
        self._epd.init()
        self._epd.Clear()
        logger.info("E-ink display initialized.")

    async def display_image(self, image: Image.Image) -> None:
        if self._epd is None:
            await self.init()
        await asyncio.to_thread(self._display_sync, image)

    def _display_sync(self, image: Image.Image) -> None:
        buf = self._epd.getbuffer(image)
        self._epd.display(buf)
        self._epd.sleep()

    async def clear(self) -> None:
        if self._epd:
            await asyncio.to_thread(self._epd.Clear)

    async def shutdown(self) -> None:
        if self._epd:
            await asyncio.to_thread(self._epd.sleep)
