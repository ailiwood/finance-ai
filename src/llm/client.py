"""Unified LLM client — OpenAI-compatible /chat/completions protocol."""

from __future__ import annotations

from typing import Optional
import httpx

from .providers import PROVIDERS, get_provider


class LLMClient:
    """Unified client for any OpenAI-compatible LLM provider."""

    def __init__(
        self,
        provider_key: str,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        cfg = get_provider(provider_key)
        self.provider_key = provider_key
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.model = model or (cfg["models"][0] if cfg["models"] else "")
        self.api_key = api_key

    def chat(
        self,
        system: str = "",
        user: str = "",
        temperature: float = 0.7,
        timeout: int = 120,
    ) -> str:
        """Send a chat completion request.

        Returns:
            The assistant's reply text.

        Raises:
            httpx.HTTPError on failure (with Chinese-friendly messages).
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }

        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            raise ConnectionError("连接超时，请检查网络或更换供应商")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise PermissionError("API Key 无效或余额不足")
            elif e.response.status_code == 429:
                raise RuntimeError("请求频率过高，请稍后重试")
            elif e.response.status_code >= 500:
                raise ConnectionError(f"服务器错误 ({e.response.status_code})，请稍后重试")
            raise RuntimeError(f"请求失败 ({e.response.status_code})")
        except httpx.ConnectError:
            raise ConnectionError("无法连接到此供应商地址，请检查 base_url")


def test_connection(
    provider_key: str,
    api_key: str,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 15,
) -> tuple[bool, str]:
    """Test LLM connection with a minimal request.

    Returns:
        (success: bool, message: str) — Chinese messages for UI display.
    """
    try:
        client = LLMClient(provider_key, api_key, base_url, model)
        reply = client.chat(
            system="Reply with exactly: OK",
            user="ping",
            temperature=0,
            timeout=timeout,
        )
        if "OK" in reply.upper():
            return True, f"连接成功 ({client.model})"
        return True, f"连接成功但回复异常: {reply[:50]}"
    except ConnectionError as e:
        return False, str(e)
    except PermissionError as e:
        return False, str(e)
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"连接测试失败: {str(e)[:100]}"
