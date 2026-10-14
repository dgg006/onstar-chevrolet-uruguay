"""Fuel and odometer sensors with original vehicle timestamps."""
import math
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN

# key, label, unit (None for text), icon, precision, experimental
SENSORS = (
    ("ODO_READ", "Kilometraje", "km", "mdi:counter", 1, False),
    ("FUEL_LEVEL", "Combustible", "%", "mdi:gas-station", 1, False),
    ("FUEL_REMAINING", "Combustible restante", "L", "mdi:gas-station", 2, False),
    ("FUEL_RANGE", "Autonomía", "km", "mdi:map-marker-distance", 1, False),
    ("AVERAGE_FUEL_ECONOMY", "Consumo promedio", "L/100km", "mdi:gas-station", 2, False),
    ("TRIP_A_ODO", "Kilometraje parcial A", "km", "mdi:counter", 1, False),
    ("EOL_READ", "Vida del aceite", "%", "mdi:oil", 0, False),
    ("FUEL_USED", "Combustible consumido", "L", "mdi:gas-station", 2, False),
    ("FUEL_CAPACITY", "Capacidad del tanque", "L", "mdi:gas-station", 1, False),
    ("BATT_SAVER_MODE_COUNTER", "Contador de ahorro de batería", "", "mdi:battery", 0, False),
    ("BATT_SAVER_MODE_SEV_LVL", "Nivel de ahorro de batería", "", "mdi:battery", 0, False),
    ("FRONT_PLACARD", "Presión recomendada delantera", "kPa", "mdi:car-tire-alert", 0, False),
    ("REAR_PLACARD", "Presión recomendada trasera", "kPa", "mdi:car-tire-alert", 0, False),
    ("FRONT_PLACARD_IN_PSI", "Presión recomendada delantera PSI", "psi", "mdi:car-tire-alert", 0, False),
    ("REAR_PLACARD_IN_PSI", "Presión recomendada trasera PSI", "psi", "mdi:car-tire-alert", 0, False),
    ("ENGINE_TYPE", "Tipo de motor", None, "mdi:engine", None, False),
    ("WINDOW_POSITION_STATUS", "Posición de ventanas (experimental)", None, "mdi:car-door", None, True),
    ("DRIVER_DOOR_OPEN_STATUS_AUTHENTICATED", "Puerta del conductor (experimental)", None, "mdi:car-door", None, True),
    ("LEFT_REAR_DOOR_AJAR_STATUS", "Puerta trasera izquierda (experimental)", None, "mdi:car-door", None, True),
    ("RIGHT_REAR_DOOR_AJAR_STATUS", "Puerta trasera derecha (experimental)", None, "mdi:car-door", None, True),
    ("FRONT_CLOSURE_LOCK_STATUS", "Bloqueo del cierre delantero (experimental)", None, "mdi:lock-question", None, True),
    ("REAR_CLOSURE_LOCK_STATUS", "Bloqueo del cierre trasero (experimental)", None, "mdi:lock-question", None, True),
)


async def async_setup_entry(hass, entry, async_add_entities):
    state = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OnStarSensor(state, *description) for description in SENSORS])


class OnStarSensor(CoordinatorEntity, SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, state, key, name, unit, icon, precision, experimental):
        super().__init__(state["coordinator"])
        self.key = key
        self.unit = unit
        self.experimental = experimental
        self._attr_name = name
        self._attr_unique_id = state["vin"] + "_" + key.lower()
        if unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = unit or None
            self._attr_suggested_display_precision = precision
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, state["vin"])}, "name": "Chevrolet OnStar",
            "manufacturer": "Chevrolet", "model": state["vehicle"].get("model"),
        }

    @property
    def native_value(self):
        reading = self.coordinator.data["readings"].get(self.key, {})
        value = reading.get("value")
        if value is None or str(value).strip().upper() in ("", "N/A", "UNKNOWN", "UNAVAILABLE"):
            return None
        if self.unit is None:
            return "Combustión interna" if self.key == "ENGINE_TYPE" and value == "ICE" else str(value)
        actual_unit = str(reading.get("unit") or "").upper()
        if self.unit and actual_unit != self.unit.upper():
            return None
        if not self.unit and actual_unit not in ("", "N/A"):
            return None
        try:
            value = float(value)
            return value if math.isfinite(value) else None
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        reading = self.coordinator.data["readings"].get(self.key, {})
        return {"actualizado_por_vehiculo": reading.get("updated_at"),
                "unidad_original": reading.get("unit"),
                "experimental": self.experimental,
                "consulta_experimental": self.coordinator.data.get("extra_status") if self.experimental else None,
                "resultado_actualizacion": self.coordinator.data.get("refresh", {}).get("health")}
