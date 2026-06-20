"""Kronos HTTP client for the main QuantSage application.

Wraps calls to the Kronos FastAPI microservice with graceful degradation.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import warnings


class KronosClient:
    """HTTP client for Kronos prediction service.

    Usage:
        client = KronosClient("http://localhost:8100")
        if client.is_available():
            result = client.predict("600519", ohlcv_data, horizon=5)
    """

    def __init__(self, base_url: str = "http://localhost:8100", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> Optional[Dict[str, Any]]:
        """Internal GET request."""
        try:
            import requests
            resp = requests.get(
                f"{self.base_url}{path}",
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _post(self, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Internal POST request."""
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}{path}",
                json=data,
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def is_available(self) -> bool:
        """Check if the Kronos service is running and healthy."""
        result = self._get("/health")
        if result is None:
            return False
        return result.get("status") == "ok"

    def health(self) -> Optional[Dict[str, Any]]:
        """Get full health status of the Kronos service."""
        return self._get("/health")

    def gpu_status(self) -> Optional[Dict[str, Any]]:
        """Get detailed GPU status."""
        return self._get("/gpu")

    def predict(
        self,
        symbol: str,
        ohlcv: List[Dict[str, Any]],
        horizon_days: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Request a K-line price prediction.

        Args:
            symbol: Stock symbol (e.g., "600519")
            ohlcv: List of OHLCV dicts with keys: date, open, high, low, close, volume
            horizon_days: Forecast horizon in days (1-30)

        Returns:
            Prediction dict with direction, confidence, target_price, bounds,
            or None if service is unavailable.
        """
        if not self.is_available():
            warnings.warn("Kronos service is not available")
            return None

        payload = {
            "symbol": symbol,
            "ohlcv": ohlcv,
            "horizon_days": horizon_days,
        }
        return self._post("/predict", payload)

    def batch_predict(
        self,
        requests: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Batch prediction for multiple stocks.

        Args:
            requests: List of {"symbol": str, "ohlcv": [...], "horizon_days": int}

        Returns:
            Batch result dict with predictions and errors arrays.
        """
        if not self.is_available():
            warnings.warn("Kronos service is not available")
            return None

        return self._post("/batch_predict", {"symbols": requests})
