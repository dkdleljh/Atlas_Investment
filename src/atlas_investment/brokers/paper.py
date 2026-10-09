from __future__ import annotations

from atlas_investment.brokers.mock import MockBroker


class PaperBroker(MockBroker):
    """Paper broker with immediate virtual fills.

    This class intentionally never talks to a real broker.
    """

