import logging

from typing import List, Tuple

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ReactiveMesaMode, VertexCurve

setup_logging()
_log = logging.getLogger(__name__)


class WattVar(ReactiveMesaMode):
    """MESA Watt-VAr mode: look up a reactive-power target on a piecewise-linear
    watt-var curve keyed on the current active power (as a percentage of maximum active
    power). Curve y-values are percent of maximum reactive power. New native
    implementation (no Julia fallback).
    """
    def __init__(self, watt_var_curve: List[Tuple[float, float]], **kwargs):
        super(WattVar, self).__init__(**kwargs)
        self.watt_var_curve: VertexCurve = VertexCurve(watt_var_curve)

    def control_reactive(self, schedule_period, start_time, sp_progress):
        active_power = self.ess.power_command
        watt_percentage = (active_power / self.ess.maximum_power * 100) if self.ess.maximum_power else 0.0
        var_percentage = self.watt_var_curve.interpolate(watt_percentage)
        reactive_power = var_percentage / 100 * self.ess.maximum_reactive_power
        _log.debug(f'WattVar: P={active_power} ({watt_percentage}%) -> {var_percentage}% -> {reactive_power} kVAR')
        return reactive_power
