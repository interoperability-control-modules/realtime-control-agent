import logging
import math

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ReactiveMesaMode
from rt_control.use_cases.load_following import LoadFollowing
from rt_control.use_cases.peak_limiting import PeakLimiting

setup_logging()
_log = logging.getLogger(__name__)


class PowerFactorCorrection(ReactiveMesaMode):
    """MESA Power Factor Correction mode (DNP3 DPFC logical node).

    Corrects the power factor measured at a signal meter (the site / point of common
    coupling) toward an average PF target by supplying the reactive power the site needs,
    clamped so the corrected PF stays within a lower/upper PF limit band.

    The measured active power at the signal meter is read from a PeakLimiting or
    LoadFollowing use case (realtime_power). Power factors are in [-1, 1]; the sign sets
    the desired VAR direction (positive => capacitive / injecting).

    Parameters (per the DPFC mapping):
      - average_pf_target (PFTrg): PF the site should be corrected toward.
      - lower_pf_limit / upper_pf_limit (PFCorRef): PF bounds constraining the correction.

    New native implementation (no Julia fallback). Applies an instantaneous single-step
    correction; it does not model the DPFC ramp rate or reversion timers.
    """
    def __init__(self, average_pf_target: float, lower_pf_limit: float = None,
                 upper_pf_limit: float = None, **kwargs):
        super(PowerFactorCorrection, self).__init__(**kwargs)
        self.average_pf_target: float = average_pf_target
        self.lower_pf_limit: float = lower_pf_limit
        self.upper_pf_limit: float = upper_pf_limit

    def _site_active_power(self):
        peak_limiting = next((c for c in self.use_cases if isinstance(c, PeakLimiting)), None)
        if peak_limiting is not None:
            return peak_limiting.realtime_power
        load_following = next((c for c in self.use_cases if isinstance(c, LoadFollowing)), None)
        if load_following is not None:
            return load_following.realtime_power
        return None

    @staticmethod
    def _reactive_for_pf(active_power, power_factor):
        # Q = |P| * tan(acos(|pf|)), signed by the target pf's sign.
        magnitude = min(abs(power_factor), 1.0)
        reactive_magnitude = abs(active_power) * math.tan(math.acos(magnitude))
        return math.copysign(reactive_magnitude, power_factor)

    def control_reactive(self, schedule_period, start_time, sp_progress):
        active_power = self._site_active_power()
        if active_power is None:
            _log.error('PowerFactorCorrection requires a PeakLimiting or LoadFollowing use case for site power.')
            return 0.0

        # Clamp the requested PF target into the configured limit band.
        target_pf = self.average_pf_target
        if self.lower_pf_limit is not None:
            target_pf = max(target_pf, self.lower_pf_limit)
        if self.upper_pf_limit is not None:
            target_pf = min(target_pf, self.upper_pf_limit)

        reactive_power = self._reactive_for_pf(active_power, target_pf)
        # Do not exceed the ESS reactive capability.
        reactive_power = min(max(reactive_power, self.ess.minimum_reactive_power), self.ess.maximum_reactive_power)
        _log.debug(f'PowerFactorCorrection: P_site={active_power}, pf_target={target_pf} -> Q={reactive_power} kVAR')
        return reactive_power
