from __future__ import annotations

import logging
from typing import Union

from PIL import Image

from multi_agent.platform_detect import PLATFORM

logger = logging.getLogger(__name__)


class DisplayManager:
    """
    Platform-dispatching display interface.
    Automatically selects EinkDriver (RPi) or MacOSDriver (macOS).
    """

    def __init__(self, width: int = 800, height: int = 480) -> None:
        self.width = width
        self.height = height
        self._driver = self._create_driver()

    def _create_driver(self):
        if PLATFORM.is_rpi:
            from multi_agent.display.eink_driver import EinkDriver
            logger.info("Using e-ink hardware driver (RPi)")
            return EinkDriver()
        else:
            from multi_agent.display.macos_driver import MacOSDriver
            logger.info("Using macOS fallback display driver")
            return MacOSDriver()

    async def init(self) -> None:
        await self._driver.init()

    async def show(self, image: Image.Image) -> None:
        await self._driver.display_image(image)

    async def clear(self) -> None:
        await self._driver.clear()

    async def shutdown(self) -> None:
        await self._driver.shutdown()
