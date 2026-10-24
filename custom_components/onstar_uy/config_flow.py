"""Configure a single regional account via UI or YAML import."""
import uuid

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from . import DOMAIN
from .client import OnStarAuthError, OnStarError
from .const import APP_CLIENT_ID, APP_DEFAULTS
from .credentials import KEY_FILENAME, make_client, SigningKeyError, load_client_configuration


class OnStarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            values = dict(user_input)
            values.setdefault("device_id", str(uuid.uuid4()))
            values.setdefault("client_id", APP_CLIENT_ID)
            values.setdefault("scan_interval", 1800)
            try:
                values = await self._apply_advanced(values)
                client = self._client(values)
                vehicles = await self.hass.async_add_executor_job(client.vehicles)
                vin = values.get("vin")
                if not vin and len(vehicles) == 1:
                    vin = vehicles[0]["vin"]
                if not vehicles:
                    errors["base"] = "no_vehicles"
                elif not vin and len(vehicles) > 1:
                    self._pending_values = values
                    self._vehicle_choices = {}
                    for item in vehicles:
                        vehicle_vin = item.get("vin")
                        if isinstance(vehicle_vin, str) and vehicle_vin:
                            label = " ".join(str(item[k]) for k in ("make", "model", "year") if item.get(k))
                            self._vehicle_choices[vehicle_vin] = (label or "Chevrolet") + " · " + vehicle_vin[-6:]
                    if not self._vehicle_choices:
                        errors["base"] = "no_vehicles"
                    else:
                        return await self.async_step_select_vehicle()
                elif not vin or not any(item.get("vin") == vin for item in vehicles):
                    errors["base"] = "select_vehicle"
                else:
                    values["vin"] = vin
                    return self.async_create_entry(title="Chevrolet OnStar Uruguay", data=values)
            except SigningKeyError:
                errors["base"] = "client_key_error"
            except OnStarAuthError:
                errors["base"] = "invalid_auth"
            except OnStarError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional("advanced"): self._advanced_schema(APP_DEFAULTS),
        }), errors=errors)

    def _advanced_schema(self, current):
        # Secrets are deliberately never returned as form defaults.
        return section(vol.Schema({
            vol.Optional("client_id", default=current["client_id"]): str,
            vol.Optional("client_secret"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional("app_version", default=current["app_version"]): str,
        }), {"collapsed": True})

    async def _configuration(self, values):
        return await self.hass.async_add_executor_job(
            load_client_configuration, values, self.hass.config.path(KEY_FILENAME))

    async def _apply_advanced(self, values):
        values = dict(values)
        advanced = values.pop("advanced", {})
        if not advanced:
            return values
        repairing = False
        try:
            current = await self._configuration(values)
        except SigningKeyError:
            if not advanced.get("client_secret"):
                raise
            current = dict(APP_DEFAULTS)
            repairing = True
        changed_id = advanced.get("client_id", current["client_id"]) != current["client_id"]
        if changed_id and not advanced.get("client_secret", "").strip():
            raise SigningKeyError("Al cambiar el cliente, completá su clave correspondiente")
        updates = {key: value for key, value in advanced.items() if value}
        if repairing or any(value != current.get(key) for key, value in updates.items()):
            current.update(updates)
            values.update(current, client_configuration_override=True)
        return values

    def _client(self, values):
        return make_client(values, self.hass.config.path(KEY_FILENAME))

    async def async_step_select_vehicle(self, user_input=None):
        errors = {}
        if user_input is not None:
            vin = user_input.get("vin")
            if vin in self._vehicle_choices:
                values = dict(self._pending_values, vin=vin)
                return self.async_create_entry(title="Chevrolet OnStar Uruguay", data=values)
            errors["base"] = "select_vehicle"
        return self.async_show_form(step_id="select_vehicle", data_schema=vol.Schema({
            vol.Required("vin"): vol.In(self._vehicle_choices),
        }), errors=errors)

    async def async_step_import(self, user_input):
        return await self.async_step_user(user_input)

    async def async_step_reauth(self, entry_data):
        """Ask for a replacement password after an authentication failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            values = dict(entry.data, password=user_input["password"])
            try:
                client = self._client(values)
                vehicles = await self.hass.async_add_executor_job(client.vehicles)
                if not any(item.get("vin") == values.get("vin") for item in vehicles):
                    errors["base"] = "select_vehicle"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={"password": values["password"]})
            except SigningKeyError:
                errors["base"] = "client_key_error"
            except OnStarAuthError:
                errors["base"] = "invalid_auth"
            except OnStarError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({
            vol.Required("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            values = dict(entry.data)
            # Empty optional secret fields preserve the existing value.
            values.update({key: value for key, value in user_input.items()
                           if value or key not in ("password", "client_secret")})
            try:
                values = await self._apply_advanced(values)
                client = self._client(values)
                vehicles = await self.hass.async_add_executor_job(client.vehicles)
                if not any(item.get("vin") == values.get("vin") for item in vehicles):
                    errors["base"] = "select_vehicle"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates=values)
            except SigningKeyError:
                errors["base"] = "client_key_error"
            except OnStarAuthError:
                errors["base"] = "invalid_auth"
            except OnStarError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema({
            vol.Optional("password"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional("scan_interval", default=entry.data.get("scan_interval", 1800)):
                vol.All(vol.Coerce(int), vol.Range(min=300, max=86400)),
            vol.Optional("auto_refresh", default=entry.data.get("auto_refresh", True)): bool,
            vol.Optional("advanced"): self._advanced_schema(await self._form_configuration(entry.data)),
        }), errors=errors)

    async def _form_configuration(self, values):
        try:
            return await self._configuration(values)
        except SigningKeyError:
            return dict(APP_DEFAULTS)
