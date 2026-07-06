import asyncio
import base64
import json as _json
import random
import time
from typing import Any

import httpx

from app.config import settings
from app.session import UserSession


class AuthError(Exception):
    pass


class AlsoEnergyClient:
    """Stateless HTTP client — all auth state (token, credentials) lives on the
    UserSession passed into every call, never on this object, so one tenant's
    session can never read or refresh another tenant's token."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.alsoenergy_base_url,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def authenticate_with(self, username: str, password: str) -> tuple[str, float]:
        """Authenticate with explicit credentials. Returns (access_token, expires_at_monotonic)."""
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
        }
        resp = await self._http.post("/Auth/token", data=data)
        resp.raise_for_status()
        payload = resp.json()
        access_token = payload["access_token"]
        return access_token, self._jwt_exp(access_token)

    @staticmethod
    def _jwt_exp(token: str) -> float:
        """Extract exp claim from a JWT without verifying the signature."""
        try:
            part = token.split(".")[1]
            part += "=" * (-len(part) % 4)
            claims = _json.loads(base64.urlsafe_b64decode(part))
            exp_unix = claims["exp"]
            return time.monotonic() + (exp_unix - time.time())
        except Exception:
            return time.monotonic() + 900

    async def _ensure_token(self, user: UserSession) -> None:
        if not user.has_credentials():
            raise AuthError("No credentials configured for this session. Please complete onboarding.")
        needs_refresh = user.access_token is None or time.monotonic() >= user.token_expires_at - 60
        if needs_refresh:
            token, expires_at = await self.authenticate_with(user.username, user.password)
            user.access_token = token
            user.token_expires_at = expires_at

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _request(self, user: UserSession, method: str, path: str, **kwargs) -> Any:
        await self._ensure_token(user)

        last_exc: Exception | None = None
        for attempt in range(5):  # 0..4 → 4 retries after first attempt
            headers = {"Authorization": f"Bearer {user.access_token}"}
            try:
                resp = await self._http.request(method, path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                await self._backoff(attempt)
                continue

            if resp.status_code == 401:
                token, expires_at = await self.authenticate_with(user.username, user.password)
                user.access_token = token
                user.token_expires_at = expires_at
                headers = {"Authorization": f"Bearer {user.access_token}"}
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
    # API methods — every call is scoped to the caller's UserSession
    # ------------------------------------------------------------------

    async def get_sites(self, user: UserSession) -> list[dict]:
        """Fetch all sites, handling paginated { items, totalCount } responses."""
        page, size = 1, 100
        results: list[dict] = []
        while True:
            resp = await self._request(user, "GET", "/Sites", params={"page": page, "pageSize": size})
            if isinstance(resp, list):
                return resp
            items = resp.get("items", [])
            results.extend(items)
            total = resp.get("totalCount", len(results))
            if len(results) >= total or not items:
                break
            page += 1
        return results

    async def get_site(self, user: UserSession, site_id: int | str) -> dict:
        return await self._request(user, "GET", f"/Sites/{site_id}")

    async def get_site_hardware(
        self,
        user: UserSession,
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
        return await self._request(user, "GET", f"/Sites/{site_id}/Hardware", params=params)

    async def get_hardware(self, user: UserSession, hardware_id: int | str) -> dict:
        return await self._request(user, "GET", f"/Hardware/{hardware_id}")

    async def get_gateway_devices_config(self, user: UserSession, gateway_id: str) -> dict:
        return await self._request(
            user,
            "GET",
            f"/Gateways/{gateway_id}/Devices/Config",
            params={"withGatewayCommands": "true"},
        )

    async def close(self) -> None:
        await self._http.aclose()


# Singleton — safe to share because it holds no per-tenant state (see class docstring).
client = AlsoEnergyClient()
