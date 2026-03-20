"""Simulation bots / virtual agents — all run in simulation mode only."""

from backend.bots.base_bot import BaseBot, BotInput, BotOutput
from backend.bots.price_action_bot import PriceActionBot
from backend.bots.options_reaction_bot import OptionsReactionBot
from backend.bots.squeeze_bot import SqueezeBot
from backend.bots.funding_stress_bot import FundingStressBot
from backend.bots.macro_shock_bot import MacroShockBot
from backend.bots.strategy_bot import StrategyBot
from backend.bots.trade_decision_bot import TradeDecisionBot
from backend.bots.regime_bot import RegimeBot

__all__ = [
    "BaseBot", "BotInput", "BotOutput",
    "PriceActionBot",
    "OptionsReactionBot",
    "SqueezeBot",
    "FundingStressBot",
    "MacroShockBot",
    "StrategyBot",
    "TradeDecisionBot",
    "RegimeBot",
]
