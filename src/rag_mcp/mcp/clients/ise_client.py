"""ISE (Indian Stock Exchange) MCP client with convenience methods."""

import logging

from rag_mcp.mcp.clients.http_client import HTTPMCPClient, MCPClientError
from rag_mcp.mcp.models import MCPResponse


class ISEMCPClient(HTTPMCPClient):
    """Specialized MCP client for ISE (NSE/BSE) stock market data."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """Initialize ISE MCP client.

        Args:
            base_url: Base URL of ISE MCP server.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
        """
        super().__init__(base_url, api_key, timeout)
        self.logger = logging.getLogger(__name__)

    async def get_stock_data(self, name: str) -> dict:
        """Get stock data for a given stock name.

        Args:
            name: Stock name or symbol.

        Returns:
            dict: Stock data from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting stock data for %s", name)
        response = await self.call_tool(
            "get_stock_data",
            {"name": name},
        )
        return response.result or {}

    async def get_trending_stocks(self) -> dict:
        """Get trending stocks.

        Returns:
            dict: Trending stocks data from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting trending stocks")
        response = await self.call_tool(
            "get_trending_stocks",
            {},
        )
        return response.result or {}

    async def get_52_week_high_low(self) -> dict:
        """Get 52-week high/low stocks.

        Returns:
            dict: 52-week high/low data from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting 52-week high/low stocks")
        response = await self.call_tool(
            "get_52_week_high_low",
            {},
        )
        return response.result or {}

    async def get_nse_most_active(self) -> dict:
        """Get most active NSE stocks.

        Returns:
            dict: Most active NSE stocks from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting most active NSE stocks")
        response = await self.call_tool(
            "get_nse_most_active",
            {},
        )
        return response.result or {}

    async def get_bse_most_active(self) -> dict:
        """Get most active BSE stocks.

        Returns:
            dict: Most active BSE stocks from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting most active BSE stocks")
        response = await self.call_tool(
            "get_bse_most_active",
            {},
        )
        return response.result or {}

    async def get_mutual_funds(self) -> dict:
        """Get mutual fund data.

        Returns:
            dict: Mutual fund data from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting mutual funds data")
        response = await self.call_tool(
            "get_mutual_funds",
            {},
        )
        return response.result or {}

    async def get_commodities(self) -> dict:
        """Get commodities data.

        Returns:
            dict: Commodities data from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting commodities data")
        response = await self.call_tool(
            "get_commodities",
            {},
        )
        return response.result or {}

    async def search_industry(self, industry: str) -> dict:
        """Search stocks by industry.

        Args:
            industry: Industry name to search.

        Returns:
            dict: Industry search results from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Searching industry: %s", industry)
        response = await self.call_tool(
            "search_industry",
            {"industry": industry},
        )
        return response.result or {}

    async def get_analyst_recommendations(self, symbol: str) -> dict:
        """Get analyst recommendations for a stock.

        Args:
            symbol: Stock symbol.

        Returns:
            dict: Analyst recommendations from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting analyst recommendations for %s", symbol)
        response = await self.call_tool(
            "get_analyst_recommendations",
            {"symbol": symbol},
        )
        return response.result or {}

    async def get_historical_data(self, symbol: str, **kwargs: object) -> dict:
        """Get historical data for a stock.

        Args:
            symbol: Stock symbol.
            **kwargs: Additional parameters (e.g., period, interval).

        Returns:
            dict: Historical data from MCP server.

        Raises:
            MCPClientError: If the call fails.
        """
        self.logger.debug("Getting historical data for %s", symbol)
        params: dict[str, object] = {"symbol": symbol}
        params.update(kwargs)
        response = await self.call_tool(
            "get_historical_data",
            params,
        )
        return response.result or {}

