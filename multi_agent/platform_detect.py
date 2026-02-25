from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass
class PlatformInfo:
    is_macos: bool
    is_rpi: bool
    system: str
    node: str


def detect_platform() -> PlatformInfo:
    system = platform.system()
    node = platform.node()
    is_macos = system == "Darwin"
    is_rpi = system == "Linux"
    return PlatformInfo(
        is_macos=is_macos,
        is_rpi=is_rpi,
        system=system,
        node=node,
    )


PLATFORM = detect_platform()
