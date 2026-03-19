"""Base simulation bot interface."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BotInput:
    """Standard input for all simulation bots."""
    ticker: str = "UPST"
    current_price: float = 0.0
    scenario_params: dict = field(default_factory=dict)
    market_data: dict = field(default_factory=dict)
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))


@dataclass
class BotOutput:
    """Standard output from all simulation bots."""
    bot_name: str
    run_time: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    results: dict = field(default_factory=dict)
    charts: list[dict] = field(default_factory=list)  # Chart specifications
    tables: list[dict] = field(default_factory=list)  # Table data
    paths: list[list[float]] = field(default_factory=list)  # Simulated paths
    assumptions: dict = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    confidence: float = 0.5
    explanation: str = ""
    is_simulation: bool = True  # Always true — safety flag


class BaseBot(ABC):
    """Abstract base for all simulation bots."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def run(self, input: BotInput) -> BotOutput:
        ...

    def _create_output(self, **kwargs) -> BotOutput:
        return BotOutput(bot_name=self.name, is_simulation=True, **kwargs)
