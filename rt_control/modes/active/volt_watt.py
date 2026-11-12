import logging

from datetime import timedelta
from typing import List, Tuple, Union

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import MesaMode, RampParams, VertexCurve
from rt_control.use_cases.voltage_control import VoltageControl

setup_logging()
_log = logging.getLogger(__name__)


class VoltWatt(MesaMode):
    # Native implementation of the MESA Volt-Watt mode. The Julia ctrl-eval-engine body
    # is an unimplemented stub, so this is derived from the MESA-ESS spec: the metered
    # voltage (offset by reference_voltage_offset) is looked up on a piecewise-linear
    # volt-watt curve to produce a target active power (percent of maximum power). A
    # deadband around the reference voltage produces zero response. Set use_julia=True
    # to fall back to the (stub) pyjulia implementation.
    def __init__(self, reference_voltage_offset: float, volt_watt_curve: List[Tuple[float, float]],
                 gradient: float, filter_time: Union[float, timedelta],
                 lower_deadband: float, upper_deadband: float, ramp_params: dict = None,
                 use_julia: bool = False, **kwargs):
        super(VoltWatt, self).__init__(**kwargs)
        self.reference_voltage_offset: float = reference_voltage_offset
        self.volt_watt_curve: VertexCurve = VertexCurve(volt_watt_curve)
        self.gradient: float = gradient
        self.filter_time: timedelta = timedelta(seconds=filter_time) \
            if not isinstance(filter_time, timedelta) else filter_time
        self.lower_deadband: float = lower_deadband
        self.upper_deadband: float = upper_deadband
        self.ramp_params: RampParams = RampParams(**(ramp_params or {}))
        self.use_julia: bool = use_julia

    def control(self, schedule_period, start_time, sp_progress):
        if self.use_julia:
            return self._julia_control(schedule_period, start_time, sp_progress)

        voltage_control = next((c for c in self.use_cases if isinstance(c, VoltageControl)), None)
        if voltage_control is None:
            _log.error('Volt-Watt mode requires a VoltageControl use case for the metered voltage input.')
            return 0.0

        measured_voltage = voltage_control.metered_voltage + self.reference_voltage_offset
        reference_voltage = voltage_control.reference_voltage
        # Inside the deadband about the reference voltage, produce no response.
        if reference_voltage - self.lower_deadband <= measured_voltage <= reference_voltage + self.upper_deadband:
            target_power = 0.0
        else:
            # Curve yields percent of maximum power for the measured voltage.
            watt_percentage = self.volt_watt_curve.interpolate(measured_voltage)
            target_power = watt_percentage / 100 * self.ess.maximum_power

        current_power = self.wip[-1]
        ramp_limited_power = self.ramp_params.apply_ramps(self.ess, current_power, target_power)
        energy_limited_power = self.controller.apply_energy_limits(ramp_limited_power, self.controller.resolution)
        _log.debug(f'VoltWatt: V={measured_voltage}, target={target_power}, out={energy_limited_power}')
        return energy_limited_power

    def _get_julia_mode_struct(self):
        from julia.api import LibJulia
        api = LibJulia.load(julia='/home/volttron/PyJuliaTesting/julia-1.10.4/bin/julia')
        api.init_julia(['--project=/home/volttron/PyJuliaTesting/ctrl-eval-engine-app'])
        from julia.CtrlEvalEngine.EnergyStorageRTControl import VoltWattMode, MesaModeParams, Vertex
        from julia.CtrlEvalEngine.EnergyStorageRTControl import VertexCurve as JuliaVertexCurve
        mesa_mode_params = MesaModeParams(self.priority)
        curve = JuliaVertexCurve([Vertex(v.x, v.y) for v in self.volt_watt_curve.vertices])
        return VoltWattMode(mesa_mode_params, self.reference_voltage_offset, curve,
                            self.gradient, self.filter_time, self.lower_deadband, self.upper_deadband)
