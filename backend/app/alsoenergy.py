import asyncio
import base64
import json as _json
import random
import time
from typing import Any

import httpx

from app.config import settings


class AuthError(Exception):
    pass


class AlsoEnergyClient:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self._http = httpx.AsyncClient(
            base_url=settings.alsoenergy_base_url,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def authenticate(self) -> None:
        """Authenticate using keyring credentials (packaged) or .env (dev)."""
        username, password = self._resolve_credentials()
        if not username or not password:
            raise AuthError("No credentials configured. Please complete onboarding.")
        await self._authenticate_with(username, password)

    async def _authenticate_with(self, username: str, password: str) -> None:
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
        }
        resp = await self._http.post("/Auth/token", data=data)
        resp.raise_for_status()
        self._store_tokens(resp.json())

    @staticmethod
    def _resolve_credentials() -> tuple[str, str]:
        """Return (username, password) from keyring first, .env fallback."""
        import sys
        if getattr(sys, "frozen", False):
            from app.credentials import load
            return load()
        # Dev mode: use .env via settings
        return (settings.alsoenergy_username, settings.alsoenergy_password)

    async def refresh(self) -> None:
        # API tokens are short-lived (15 min rolling); just re-auth with password.
        await self.authenticate()

    def _store_tokens(self, payload: dict) -> None:
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        # API doesn't return expires_in; decode exp from the JWT directly.
        self._expires_at = self._jwt_exp(payload["access_token"])

    @staticmethod
    def _jwt_exp(token: str) -> float:
        """Extract exp claim from a JWT without verifying the signature."""
        try:
            part = token.split(".")[1]
            # Add padding so base64 doesn't choke
            part += "=" * (-len(part) % 4)
            claims = _json.loads(base64.urlsafe_b64decode(part))
            exp_unix = claims["exp"]
            # Convert absolute unix timestamp → monotonic equivalent
            return time.monotonic() + (exp_unix - time.time())
        except Exception:
            # Fallback: assume 15 minutes
            return time.monotonic() + 900

    def _token_needs_refresh(self) -> bool:
        return time.monotonic() >= self._expires_at - 60

    async def _ensure_token(self) -> None:
        if self._access_token is None:
            await self.authenticate()
        elif self._token_needs_refresh():
            await self.refresh()

    @property
    def token_status(self) -> dict:
        if self._access_token is None:
            return {"status": "not_authenticated"}
        if self._token_needs_refresh():
            return {"status": "expired"}
        remaining = int(self._expires_at - time.monotonic())
        return {"status": "valid", "expires_in_seconds": remaining}

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        await self._ensure_token()

        last_exc: Exception | None = None
        for attempt in range(5):  # 0..4 → 4 retries after first attempt
            headers = {"Authorization": f"Bearer {self._access_token}"}
            try:
                resp = await self._http.request(method, path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                await self._backoff(attempt)
                continue

            if resp.status_code == 401:
                await self.refresh()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = await self._http.request(method, path, headers=headers, **kwargs)
                if resp.status_code == 401:
                    raise AuthError("Authentication failed after token refresh")

            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
                await self._backoff(attempt)
                continue

            resp.raise_for_status()
            return resp.json()

        raise last_exc or RuntimeError("Request failed after retries")

    @staticmethod
    async def _backoff(attempt: int) -> None:
        delay = min(2**attempt, 8) + random.uniform(0, 0.5)
        await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    async def get_sites(self) -> list[dict]:
        """Fetch all sites, handling paginated { items, totalCount } responses."""
        page, size = 1, 100
        results: list[dict] = []
        while True:
            resp = await self._request("GET", "/Sites", params={"page": page, "pageSize": size})
            if isinstance(resp, list):
                return resp
            items = resp.get("items", [])
            results.extend(items)
            total = resp.get("totalCount", len(results))
            if len(results) >= total or not items:
                break
            page += 1
        return results

    async def get_site(self, site_id: int | str) -> dict:
        return await self._request("GET", f"/Sites/{site_id}")

    async def get_site_hardware(
        self,
        site_id: int | str,
        include_archived_fields: bool = True,
        include_device_config: bool = True,
        include_summary_fields: bool = True,
        include_data_name_fields: bool = True,
        include_disabled: bool = False,
    ) -> dict:
        params: dict[str, Any] = {
            "includeArchivedFields": str(include_archived_fields).lower(),
            "includeDeviceConfig": str(include_device_config).lower(),
            "includeSummaryFields": str(include_summary_fields).lower(),
            "includeDataNameFields": str(include_data_name_fields).lower(),
        }
        if include_disabled:
            params["includeDisabledHardware"] = "true"
        return await self._request("GET", f"/Sites/{site_id}/Hardware", params=params)

    async def get_hardware(self, hardware_id: int | str) -> dict:
        return await self._request("GET", f"/Hardware/{hardware_id}")

    async def get_gateway_devices_config(self, gateway_id: str) -> dict:
        return await self._request(
            "GET",
            f"/Gateways/{gateway_id}/Devices/Config",
            params={"withGatewayCommands": "true"},
        )

    async def close(self) -> None:
        await self._http.aclose()


# Singleton used throughout the app lifecycle
client = AlsoEnergyClient()
