"""I1: Connector registry — string anahtarla connector instance al."""
from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.logo_tiger import LogoTigerConnector
from app.connectors.mikro import MikroConnector
from app.connectors.netsis import NetsisConnector


CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "logo_tiger": LogoTigerConnector,
    "mikro": MikroConnector,
    "netsis": NetsisConnector,
}


def get_connector(connector_type: str) -> BaseConnector:
    """Connector type string → instantiated connector.

    Raises:
        ValueError: bilinmeyen connector tipi.
    """
    cls = CONNECTOR_REGISTRY.get(connector_type)
    if cls is None:
        known = ", ".join(sorted(CONNECTOR_REGISTRY.keys()))
        raise ValueError(
            f"Bilinmeyen connector: {connector_type!r}. Mevcut: {known}"
        )
    return cls()
