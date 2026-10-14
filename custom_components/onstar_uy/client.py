"""Regional OnStar client, based on observed myChevrolet 8.19 requests."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_BASE = "https://api.lam.ext.gm.com"
SCOPE = "onstar gmoc user_trailer user msso priv role_owner"
CONTROLS = {
    "lock": ("lock", {"lockDoorRequest": {"delay": 0}}),
    "unlock": ("unlock", {"unlockDoorRequest": {"delay": 0}}),
    "flash": ("alert", {"action": ["Flash"], "override": ["DoorOpen", "IgnitionOn"], "delay": 0, "duration": 1}),
    "honk": ("alert", {"action": ["Honk"], "override": ["DoorOpen", "IgnitionOn"], "delay": 0, "duration": 1}),
    "cancel_flash": ("cancelAlert", None),
    "cancel_honk": ("cancelAlert", None),
}


class OnStarError(Exception):
    """A safe error message without account identifiers or response bodies."""


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def sign_payload(payload: dict, client_secret: str) -> str:
    header = _b64(b'{"typ":"JWS","alg":"HS256"}')
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    unsigned = header + "." + body
    signature = hmac.new(client_secret.encode(), unsigned.encode(), hashlib.sha256).digest()
    return unsigned + "." + _b64(signature)


def decode_response(body: str) -> dict:
    """Read JSON or GM's JWT envelope delivered over authenticated HTTPS."""
    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        parts = body.strip().split(".")
        if len(parts) != 3:
            raise OnStarError("Formato de respuesta de autenticación desconocido") from None
        try:
            result = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        except (ValueError, UnicodeDecodeError):
            raise OnStarError("Respuesta de autenticación inválida") from None
    if not isinstance(result, dict):
        raise OnStarError("Se esperaba una respuesta de objeto")
    return result


def health_readings(health: dict) -> dict:
    """Keep the unit and vehicle timestamp, including legitimate zero values."""
    readings = {}
    for group in health.get("diagnostics", []):
        for element in group.get("diagnosticElements", []):
            name = element.get("name")
            if name:
                readings[name] = {
                    "value": element.get("value"),
                    "unit": element.get("uom"),
                    "updated_at": element.get("cts") or group.get("cts") or health.get("cts"),
                }
    return readings


class OnStarClient:
    """Blocking regional client: call through HA's executor."""

    def __init__(self, username: str, password: str, client_secret: str,
                 device_id: str, client_id: str = "OMB_CVY_AND_8T0", client_secret_loader=None,
                 app_version: str = "8.19.0"):
        self.username = username
        self.password = password
        self.client_secret = client_secret
        self.device_id = device_id
        self.client_id = client_id
        self.app_version = app_version
        self._client_secret_loader = client_secret_loader
        self._token = None
        self._expires = 0.0
        self._last_refresh = float("-inf")
        self._refresh_result = None

    def _request(self, path: str, data: bytes | None = None,
                 token: str | None = None, method: str | None = None) -> tuple[int, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "text/plain" if path == "/api/v1/oauth/token" else "application/json",
            "locale": "es_UY",
            "Accept-Language": "es-UY",
            "appVersion": f"myOwner-chevrolet-android-{self.app_version}-0",
            "channel": "MOBILE",
            "app": "myChevrolet",
            "app-version": self.app_version,
        }
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
        try:
            # Do not forward credentials or bearer tokens to redirect destinations.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                    return None
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(request, timeout=40) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read().decode("utf-8", errors="replace")
        except (OSError, urllib.error.URLError):
            raise OnStarError("No se pudo conectar con el servidor regional de OnStar") from None

    def login(self) -> dict:
        signing_key = self._client_secret_loader() if self._client_secret_loader else self.client_secret
        payload = {
            "scope": SCOPE, "device_id": self.device_id, "client_id": self.client_id,
            "username": self.username, "password": self.password,
            "nonce": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "grant_type": "password",
        }
        status, body = self._request("/api/v1/oauth/token", sign_payload(payload, signing_key).encode())
        if status != 200:
            self._token = None
            raise OnStarError(f"OnStar rechazó el acceso (HTTP {status})")
        answer = decode_response(body)
        if not answer.get("access_token") or "onstar" not in answer.get("scope", "").split():
            self._token = None
            raise OnStarError("La sesión no recibió permiso OnStar")
        try:
            lifetime = float(answer["expires_in"])
            if lifetime <= 0:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise OnStarError("Caducidad de sesión inválida") from None
        self._token = answer["access_token"]
        self._expires = time.monotonic() + max(0, lifetime - 60)
        return {"scope": answer.get("scope"), "expires_in": lifetime}

    def get(self, path: str) -> dict:
        return self._json_request(path)

    def _json_request(self, path: str, method: str | None = None, data: bytes | None = None) -> dict:
        if not self._token or time.monotonic() >= self._expires:
            self.login()
        options = {"method": method, "data": data if data is not None else b""} if method == "POST" else {}
        status, body = self._request(path, token=self._token, **options)
        if status == 401:
            self.login()
            status, body = self._request(path, token=self._token, **options)
        if status not in (200, 202):
            raise OnStarError(f"Consulta OnStar rechazada (HTTP {status})")
        try:
            answer = json.loads(body)
        except json.JSONDecodeError:
            raise OnStarError("Formato de consulta OnStar desconocido") from None
        if not isinstance(answer, dict):
            raise OnStarError("Respuesta de consulta OnStar inválida")
        return answer

    def vehicles(self) -> list[dict]:
        vehicles = self.get("/api/v1/account/vehicles").get("vehicles", {}).get("vehicle", [])
        return [vehicles] if isinstance(vehicles, dict) else vehicles

    def control(self, vin: str, action: str, timeout: float = 75, interval: float = 3) -> str:
        """Send one physical command, without retrying an uncertain submission.

        Cancellation aliases use the same observed cancelAlert route. Command
        completion does not provide an independent door or window state.
        """
        if action not in CONTROLS or not vin:
            raise OnStarError("Control o vehículo inválido")
        if not self._token or time.monotonic() >= self._expires:
            self.login()
        token = self._token
        command, payload = CONTROLS[action]
        path = "/veh/cmd/v3/" + command + "/" + urllib.parse.quote(vin, safe="")
        data = json.dumps(payload).encode() if payload is not None else b""
        status, body = self._request(path, data=data, token=token, method="POST")
        if status not in (200, 202):
            raise OnStarError(f"OnStar rechazó el control (HTTP {status})")
        try:
            answer = json.loads(body)
            request_id = answer["requestId"]
            if not isinstance(request_id, str) or not request_id:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise OnStarError("Orden enviada sin confirmación válida; no se repitió") from None
        path = "/veh/cmd/v3/history/" + command + "/requests/" + urllib.parse.quote(request_id, safe="")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status, body = self._request(path, token=token)
            if status != 200:
                raise OnStarError(f"No se pudo confirmar el control (HTTP {status}); no se repitió")
            try:
                result = str(json.loads(body)["status"])
            except (ValueError, KeyError, TypeError):
                raise OnStarError("Respuesta de confirmación inválida; no se repitió") from None
            if result == "SUCCESS":
                return result
            if result not in ("IN_PROGRESS", "PENDING", "QUEUED", "REQUESTED"):
                raise OnStarError("OnStar no confirmó la ejecución del control")
            time.sleep(interval)
        raise OnStarError("Terminó la espera sin confirmación; la orden pudo ejecutarse y no se repitió")

    def health(self, vin: str) -> dict:
        return self.get("/api/v1/vh/vehiclehealth/v1/healthstatus/" + urllib.parse.quote(vin, safe=""))

    def extra_readings(self, vin: str) -> dict:
        """Read known schema fields; missing data remains unknown."""
        fields = ("DRIVER_DOOR_OPEN_STATUS_AUTHENTICATED", "LEFT_REAR_DOOR_AJAR_STATUS",
                  "RIGHT_REAR_DOOR_AJAR_STATUS", "FRONT_CLOSURE_LOCK_STATUS",
                  "REAR_CLOSURE_LOCK_STATUS")
        selection = " ".join(name + " { value uom cts }" for name in fields)
        query = ("query { vehicle(auth: AUTHZ, region: SA, vin: " + json.dumps(vin) +
                 ") { vehicleStatus { diagnostics { " + selection + " } } } }")
        answer = self._json_request("/veh/datadelivery/digitaltwin/gql/v1/graphql", "POST",
                                    json.dumps({"query": query}).encode())
        if answer.get("errors"):
            raise OnStarError("La consulta experimental no devolvió datos válidos")
        vehicle = (answer.get("data") or {}).get("vehicle") or {}
        diagnostics = (vehicle.get("vehicleStatus") or {}).get("diagnostics") or {}
        return {name: {"value": value.get("value"), "unit": value.get("uom"),
                       "updated_at": value.get("cts")}
                for name, value in diagnostics.items()
                if name in fields and isinstance(value, dict) and value.get("value") is not None}

    def location(self, vin: str) -> dict:
        """Read cached position without requesting an SMS refresh."""
        answer = self.get("/veh/datadelivery/digitaltwin/v1/vehicles/" +
                          urllib.parse.quote(vin, safe="") + "?sms=false")
        try:
            telemetry = answer["telemetry"]
            position = telemetry["data"]["position"]
            lat, lng = float(position["lat"]), float(position["lng"])
            if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise OnStarError("OnStar no devolvió una ubicación válida") from None
        return {"latitude": lat, "longitude": lng, "updated_at": telemetry.get("occurredTs"),
                "update_pending": telemetry.get("data", {}).get("session", {}).get("updatePending")}

    def refresh(self, vin: str, timeout: float = 75, interval: float = 3) -> dict:
        """Request fresh diagnostics and GPS, then poll known regional routes.

        HTTP 202 only acknowledges a request; SUCCESS confirms completion.
        Do not follow the internal GM host returned by diagnostic requests.
        """
        if time.monotonic() - self._last_refresh < 60 and self._refresh_result is not None:
            return self._refresh_result
        self._last_refresh = time.monotonic()
        self._refresh_result = None
        encoded = urllib.parse.quote(vin, safe="")
        started = {
            "location": self._json_request("/veh/cmd/v3/location/" + encoded, "POST"),
            "health": self._json_request("/vh/vehiclehealth/v1/healthstatus/probe/" + encoded, "POST"),
        }
        requests = {}
        result = {"location": "PENDING", "health": "PENDING", "position": None}
        for name, response in started.items():
            request_id = response.get("requestId")
            if not isinstance(request_id, str) or not request_id:
                raise OnStarError("La actualización no devolvió un identificador de solicitud")
            quoted = urllib.parse.quote(request_id, safe="")
            requests[name] = ("/veh/cmd/v3/history/location/requests/" + quoted if name == "location"
                              else "/vh/vehiclehealth/v1/healthstatus/probe/" + encoded + "/requests/" + quoted)
        deadline = time.monotonic() + timeout
        while requests:
            for name, path in list(requests.items()):
                if time.monotonic() >= deadline:
                    result[name] = "TIMEOUT"
                    del requests[name]
                    continue
                response = self.get(path)
                status = str(response.get("status", "UNKNOWN"))
                if status in ("IN_PROGRESS", "PENDING", "QUEUED", "REQUESTED"):
                    continue
                result[name] = status
                del requests[name]
                if name == "location" and status == "SUCCESS":
                    payload = response.get("payload") or {}
                    try:
                        lat = float(payload["location"]["lat"])
                        lng = float(payload["location"]["long"])
                        stamp = payload["timeStamp"]
                        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                        if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                            raise ValueError()
                    except (KeyError, TypeError, ValueError, AttributeError):
                        result[name] = "INVALID_RESPONSE"
                    else:
                        result["position"] = {"latitude": lat, "longitude": lng,
                                              "updated_at": stamp, "update_pending": "SUCCESS"}
            if requests:
                time.sleep(min(interval, max(0, deadline - time.monotonic())))
        self._refresh_result = result
        return result
