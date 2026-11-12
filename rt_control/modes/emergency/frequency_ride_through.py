import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import EmergencyMesaMode
from rt_control.use_cases.frequency_response import FrequencyResponse

setup_logging()
_log = logging.getLogger(__name__)


class FrequencyRideThrough(EmergencyMesaMode):
    """MESA Low/High Frequency Ride-Through emergency mode. Covers both the low and high
    sides (DNP3 DHFT logical node) via four frequency thresholds:

      - high_must_trip / low_must_trip: beyond these the DER must trip (disconnect);
        output is forced to zero.
      - high_momentary_cessation / low_momentary_cessation: within the ride-through band
        but past these thresholds, the DER must cease output (hold zero) while staying
        connected.
      - otherwise: normal ride-through, output passes through unchanged.

    New native implementation (no Julia fallback). Models the trip/cessation thresholds
    as instantaneous frequency limits (Hz); it does not model the time-duration curves
    of the full IEEE 1547 ride-through envelope or breaker reconnect timers.
    """
    def __init__(self, high_must_trip: float, low_must_trip: float,
                 high_momentary_cessation: float = None, low_momentary_cessation: float = None, **kwargs):
        super(FrequencyRideThrough, self).__init__(**kwargs)
        self.high_must_trip: float = high_must_trip
        self.low_must_trip: float = low_must_trip
        self.high_momentary_cessation: float = high_momentary_cessation \
            if high_momentary_cessation is not None else high_must_trip
        self.low_momentary_cessation: float = low_momentary_cessation \
            if low_momentary_cessation is not None else low_must_trip
        self.tripped: bool = False

    def gate(self, active_power, reactive_power, start_time):
        frequency_response = next((c for c in self.use_cases if isinstance(c, FrequencyResponse)), None)
        if frequency_response is None:
            _log.error('FrequencyRideThrough requires a FrequencyResponse use case for the metered frequency input.')
            return active_power, reactive_power
        frequency = frequency_response.metered_frequency
        if frequency >= self.high_must_trip or frequency <= self.low_must_trip:
            self.tripped = True
            _log.warning(f'FrequencyRideThrough: frequency {frequency} beyond must-trip; tripping (output 0).')
            return 0.0, 0.0
        self.tripped = False
        if frequency >= self.high_momentary_cessation or frequency <= self.low_momentary_cessation:
            _log.info(f'FrequencyRideThrough: frequency {frequency} in momentary-cessation band; holding output 0.')
            return 0.0, 0.0
        return active_power, reactive_power
