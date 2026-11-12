import logging

from typing import List, Tuple

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ReactiveMesaMode, VertexCurve
from rt_control.use_cases.voltage_control import VoltageControl

setup_logging()
_log = logging.getLogger(__name__)


class VoltVar(ReactiveMesaMode):
    """MESA Volt-VAr control mode: look up a reactive-power target on a piecewise-linear
    volt-var curve keyed on the metered voltage (optionally offset by an autonomous
    reference-voltage adjustment). Curve y-values are percent of maximum reactive power.
    New native implementation (no Julia fallback).
    """
    def __init__(self, volt_var_curve: List[Tuple[float, float]],
                 reference_voltage_offset: float = 0.0, **kwargs):
        super(VoltVar, self).__init__(**kwargs)
        self.volt_var_curve: VertexCurve = VertexCurve(volt_var_curve)
        self.reference_voltage_offset: float = reference_voltage_offset

    def control_reactive(self, schedule_period, start_time, sp_progress):
        voltage_control = next((c for c in self.use_cases if isinstance(c, VoltageControl)), None)
        if voltage_control is None:
            _log.error('Volt-VAr mode requires a VoltageControl use case for the metered voltage input.')
            return 0.0
        measured_voltage = voltage_control.metered_voltage + self.reference_voltage_offset
        var_percentage = self.volt_var_curve.interpolate(measured_voltage)
        reactive_power = var_percentage / 100 * self.ess.maximum_reactive_power
        _log.debug(f'VoltVar: V={measured_voltage} -> {var_percentage}% -> {reactive_power} kVAR')
        return reactive_power
