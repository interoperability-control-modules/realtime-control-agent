import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import EmergencyMesaMode
from rt_control.use_cases.voltage_control import VoltageControl

setup_logging()
_log = logging.getLogger(__name__)


class VoltageRideThrough(EmergencyMesaMode):
    """MESA Low/High Voltage Ride-Through emergency mode. Covers both the low and high
    sides (DNP3 DHVT logical node) via four voltage thresholds:

      - high_must_trip / low_must_trip: beyond these the DER must trip (disconnect);
        output is forced to zero.
      - high_momentary_cessation / low_momentary_cessation: within the ride-through band
        but past these thresholds, the DER must cease output (hold zero) while staying
        connected.
      - otherwise: normal ride-through, output passes through unchanged.

    New native implementation (no Julia fallback). This models the trip/cessation
    thresholds as instantaneous voltage limits; it does not model the time-duration
    curves of the full IEEE 1547 ride-through envelope or breaker reconnect timers.
    Thresholds are in the same units as the metered voltage (e.g. volts, or per-unit if
    the meter reports per-unit).
    """
    def __init__(self, high_must_trip: float, low_must_trip: float,
                 high_momentary_cessation: float = None, low_momentary_cessation: float = None, **kwargs):
        super(VoltageRideThrough, self).__init__(**kwargs)
        self.high_must_trip: float = high_must_trip
        self.low_must_trip: float = low_must_trip
        # Default the cessation thresholds to the trip thresholds (no cessation band).
        self.high_momentary_cessation: float = high_momentary_cessation \
            if high_momentary_cessation is not None else high_must_trip
        self.low_momentary_cessation: float = low_momentary_cessation \
            if low_momentary_cessation is not None else low_must_trip
        self.tripped: bool = False

    def gate(self, active_power, reactive_power, start_time):
        voltage_control = next((c for c in self.use_cases if isinstance(c, VoltageControl)), None)
        if voltage_control is None:
            _log.error('VoltageRideThrough requires a VoltageControl use case for the metered voltage input.')
            return active_power, reactive_power
        voltage = voltage_control.metered_voltage
        if voltage >= self.high_must_trip or voltage <= self.low_must_trip:
            self.tripped = True
            _log.warning(f'VoltageRideThrough: voltage {voltage} beyond must-trip; tripping (output 0).')
            return 0.0, 0.0
        self.tripped = False
        if voltage >= self.high_momentary_cessation or voltage <= self.low_momentary_cessation:
            _log.info(f'VoltageRideThrough: voltage {voltage} in momentary-cessation band; holding output 0.')
            return 0.0, 0.0
        return active_power, reactive_power
