import asyncio
import hashlib
import hmac
import importlib.util
import pathlib

# Load api.py directly: importing the package would pull in Home Assistant.
_spec = importlib.util.spec_from_file_location(
    "tuya_ir_api", pathlib.Path(__file__).parents[1] / "custom_components" / "tuya_ir_remotes" / "api.py"
)
api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api)


def test_signature_matches_tuya_scheme():
    client = api.TuyaIRClient(None, "cid", "secret", "eu")
    h = client._headers("GET", "/v1.0/token?grant_type=1", b"", "")
    sts = "\n".join(["GET", hashlib.sha256(b"").hexdigest(), "", "/v1.0/token?grant_type=1"])
    expected = hmac.new(b"secret", ("cid" + h["t"] + h["nonce"] + sts).encode(), hashlib.sha256).hexdigest().upper()
    assert h["sign"] == expected and "access_token" not in h


class _Resp:
    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self, content_type=None):
        return self._data


class _Session:
    def __init__(self, replies):
        self.replies = list(replies)

    def request(self, *a, **k):
        return _Resp(self.replies.pop(0))


def _run(client, coro):
    return asyncio.run(coro)


def test_trial_expired_is_recognised():
    s = _Session([{"success": False, "code": 28841002, "msg": "No permissions. Your subscription to cloud development plan has expired."}])
    client = api.TuyaIRClient(s, "cid", "secret", "eu")
    try:
        asyncio.run(client._raw("GET", "/x", None, ""))
    except api.TrialExpired:
        pass
    else:
        raise AssertionError("expected TrialExpired")


def test_expired_token_is_renewed_once():
    s = _Session([
        {"success": True, "result": {"access_token": "t1", "expire_time": 7200}},
        {"success": False, "code": 1010, "msg": "token invalid"},
        {"success": True, "result": {"access_token": "t2", "expire_time": 7200}},
        {"success": True, "result": [1]},
    ])
    client = api.TuyaIRClient(s, "cid", "secret", "eu")
    assert asyncio.run(client.request("GET", "/x")) == [1]
    assert client._token == "t2"
