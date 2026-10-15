"""Minimal async client for Tuya's cloud IR Control Hub API (virtual IR remotes on a Tuya IR blaster)."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)
DATA_CENTERS = {
    "eu": "https://openapi.tuyaeu.com",
    "weu": "https://openapi-weaz.tuyaeu.com",
    "us": "https://openapi.tuyaus.com",
    "eus": "https://openapi-ueaz.tuyaus.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}
# Tuya error codes meaning the cloud project itself is unusable, not just this request.
TRIAL_EXPIRED = {28841002}
AUTH_FAILED = {1004, 1010, 1011, 1106, 2009, 2017}
TOKEN_EXPIRED = {1010, 1011}


class TuyaError(Exception):
    def __init__(self, code: int | None, msg: str) -> None:
        super().__init__(f"Tuya error {code}: {msg}")
        self.code = code


class TrialExpired(TuyaError):
    """The free IoT Core trial of the cloud project has run out."""


class AuthError(TuyaError):
    """Access ID/secret refused."""


@dataclass
class IRKey:
    key: str
    key_id: int
    name: str


@dataclass
class IRRemote:
    remote_id: str
    name: str
    category_id: int
    brand: str
    keys: list[IRKey] = field(default_factory=list)


class TuyaIRClient:
    def __init__(self, session: aiohttp.ClientSession, access_id: str, secret: str, data_center: str) -> None:
        self._session = session
        self._id = access_id
        self._secret = secret.encode()
        self._base = DATA_CENTERS[data_center]
        self._token = ""
        self._token_expiry = 0.0
        self._lock = asyncio.Lock()

    def _headers(self, method: str, path: str, raw: bytes, token: str) -> dict[str, str]:
        t, nonce = str(int(time.time() * 1000)), uuid.uuid4().hex
        string_to_sign = "\n".join([method, hashlib.sha256(raw).hexdigest(), "", path])
        sign = hmac.new(self._secret, (self._id + token + t + nonce + string_to_sign).encode(), hashlib.sha256)
        headers = {
            "client_id": self._id,
            "sign": sign.hexdigest().upper(),
            "t": t,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json",
        }
        if token:
            headers["access_token"] = token
        return headers

    async def _raw(self, method: str, path: str, body: dict | None, token: str) -> Any:
        raw = json.dumps(body).encode() if body is not None else b""
        try:
            async with self._session.request(
                method, self._base + path, data=raw or None, headers=self._headers(method, path, raw, token), timeout=TIMEOUT
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise TuyaError(None, f"cannot reach Tuya cloud: {err}") from err
        if not data.get("success"):
            code, msg = data.get("code"), data.get("msg", "unknown error")
            if code in TRIAL_EXPIRED or any(w in str(msg).lower() for w in ("subscription", "trial")):
                raise TrialExpired(code, msg)
            if code in AUTH_FAILED:
                raise AuthError(code, msg)
            raise TuyaError(code, msg)
        return data.get("result")

    async def _ensure_token(self) -> str:
        async with self._lock:
            if not self._token or time.time() > self._token_expiry:
                result = await self._raw("GET", "/v1.0/token?grant_type=1", None, "")
                self._token = result["access_token"]
                self._token_expiry = time.time() + int(result.get("expire_time", 7200)) - 300
            return self._token

    async def request(self, method: str, path: str, body: dict | None = None) -> Any:
        token = await self._ensure_token()
        try:
            return await self._raw(method, path, body, token)
        except AuthError as err:
            if err.code not in TOKEN_EXPIRED:
                raise
            self._token = ""  # token revoked early: get a new one and retry once
            return await self._raw(method, path, body, await self._ensure_token())

    async def remotes(self, hub_id: str) -> list[IRRemote]:
        remotes = []
        for r in await self.request("GET", f"/v2.0/infrareds/{hub_id}/remotes") or []:
            remote = IRRemote(r["remote_id"], r.get("remote_name") or r["remote_id"], int(r["category_id"]), r.get("brand_name") or "")
            keys = await self.request("GET", f"/v2.0/infrareds/{hub_id}/remotes/{remote.remote_id}/keys") or {}
            remote.keys = [IRKey(k["key"], int(k["key_id"]), k.get("key_name") or k["key"]) for k in keys.get("key_list") or []]
            remotes.append(remote)
        return remotes

    async def press(self, hub_id: str, remote: IRRemote, key: IRKey) -> None:
        await self.request(
            "POST",
            f"/v2.0/infrareds/{hub_id}/remotes/{remote.remote_id}/raw/command",
            {"category_id": remote.category_id, "key": key.key, "key_id": key.key_id},
        )

    async def find_hubs(self) -> list[tuple[str, str]]:
        """(device id, name) of every linked device that has IR remotes."""
        devices = await self.request("GET", "/v1.0/iot-01/associated-users/devices?size=100") or {}
        hubs = []
        for d in devices.get("devices") or []:
            try:
                if await self.request("GET", f"/v2.0/infrareds/{d['id']}/remotes"):
                    hubs.append((d["id"], d.get("name") or d["id"]))
            except TuyaError as err:
                if isinstance(err, (TrialExpired, AuthError)):
                    raise
        return hubs
