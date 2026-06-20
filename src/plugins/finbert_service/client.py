"""FinBERT HTTP client for the main QuantSage application."""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import warnings


class FinBERTClient:
    """HTTP client for FinBERT sentiment service.

    Usage:
        client = FinBERTClient("http://localhost:8101")
        if client.is_available():
            result = client.analyze("公司业绩大幅增长，超出市场预期")
    """

    def __init__(self, base_url: str = "http://localhost:8101", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            import requests
            resp = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _post(self, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            import requests
            resp = requests.post(f"{self.base_url}{path}", json=data, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def is_available(self) -> bool:
        result = self._get("/health")
        return result is not None and result.get("status") == "ok"

    def health(self) -> Optional[Dict[str, Any]]:
        return self._get("/health")

    def analyze(self, text: str) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            warnings.warn("FinBERT service is not available")
            return None
        return self._post("/analyze", {"text": text})

    def batch_analyze(self, texts: List[str]) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            warnings.warn("FinBERT service is not available")
            return None
        return self._post("/batch_analyze", {"texts": texts})
