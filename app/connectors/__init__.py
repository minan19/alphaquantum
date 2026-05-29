"""I1: Connector framework — Logo Tiger + future ERP integrations."""
from app.connectors.base import (
    ConnectorMode,
    ParsedInvoice,
    ParsedCustomer,
    ParseError,
    ParseResult,
    BaseConnector,
)
from app.connectors.logo_tiger import LogoTigerConnector
from app.connectors.mikro import MikroConnector
from app.connectors.registry import CONNECTOR_REGISTRY, get_connector

__all__ = [
    "ConnectorMode",
    "ParsedInvoice",
    "ParsedCustomer",
    "ParseError",
    "ParseResult",
    "BaseConnector",
    "LogoTigerConnector",
    "MikroConnector",
    "CONNECTOR_REGISTRY",
    "get_connector",
]
