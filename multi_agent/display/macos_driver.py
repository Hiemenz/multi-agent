"""macOS fallback display driver — saves BMP to /tmp."""
from __future__ import annotations

import asyncio
import logging

from PIL import Image

logger = logging.getLogger(__name__)

_OUTPUT_PATH = "/tmp/multi_agent_display.bmp"


class MacOSDriver:
    async def init(self) -> None:
        logger.info("macOS display driver initialized (output: %s)", _OUTPUT_PATH)

    async def display_image(self, image: Image.Image) -> None:
        await asyncio.to_thread(self._save, image)

    def _save(self, image: Image.Image) -> None:
        image.save(_OUTPUT_PATH)
        logger.debug("Display image saved to %s", _OUTPUT_PATH)

    async def clear(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
