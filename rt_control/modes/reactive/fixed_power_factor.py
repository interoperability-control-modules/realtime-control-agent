import logging
import math

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ReactiveMesaMode

setup_logging()
_log = logging.getLogger(__name__)


class FixedPowerFactor(ReactiveMesaMode):
    """MESA Fixed Power Factor mode: hold a constant displacement power factor by
    deriving reactive power from the current active power command,
    Q = P * tan(acos(pf)). Separate power-factor setpoints apply when generating /
    discharging (P > 0) versus charging (P < 0), per the DNP3 DFPF.PFGnTgt / PFLoadTgt
    points. Power factors are given in [-1, 1]; the sign selects VAR direction (positive
    => capacitive / injecting). New native implementation (no Julia fallback).
    """
    def __init__(self, power_factor_generating: float, power_factor_charging: float = None, **kwargs):
        super(FixedPowerFactor, self).__init__(**kwargs)
        self.power_factor_generating: float = power_factor_generating
        # Default the charging setpoint to the generating one when not provided.
        self.power_factor_charging: float = power_factor_charging \
            if power_factor_charging is not None else power_factor_generating

    def control_reactive(self, schedule_period, start_time, sp_progress):
        active_power = self.ess.power_command
        power_factor = self.power_factor_generating if active_power >= 0 else self.power_factor_charging
        magnitude = min(abs(power_factor), 1.0)
        # tan(acos(|pf|)) scales |P| into the reactive component; pf sign sets direction.
        reactive_magnitude = abs(active_power) * math.tan(math.acos(magnitude))
        reactive_power = math.copysign(reactive_magnitude, power_factor)
        _log.debug(f'FixedPowerFactor: P={active_power}, pf={power_factor} -> Q={reactive_power} kVAR')
        return reactive_power
