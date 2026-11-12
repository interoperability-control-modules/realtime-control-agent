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
from rt_control.use_cases.frequency_response import FrequencyResponse

setup_logging()
_log = logging.getLogger(__name__)


class FrequencyWatt(MesaMode):
    # Native implementation of the MESA Frequency-Watt mode. The Julia ctrl-eval-engine
    # body is an unimplemented stub, so this is derived from the MESA-ESS spec: when the
    # metered frequency crosses the high/low starting thresholds the mode activates and
    # looks up a target active power (percent of maximum power) on a piecewise-linear
    # frequency-watt curve; it deactivates once frequency returns within the stopping
    # thresholds (hysteresis). Set use_julia=True to fall back to the (stub) pyjulia
    # implementation.
    def __init__(self, use_curves: bool, frequency_watt_curve: List[Tuple[float, float]],
                 low_hysteresis_curve: List[Tuple[float, float]], high_hysteresis_curve: List[Tuple[float, float]],
                 start_delay: Union[timedelta, float], stop_delay: Union[timedelta, float],
                 minimum_soc: float, maximum_soc: float, use_hysteresis: bool, use_snapshot_power: bool,
                 high_starting_frequency: float, low_starting_frequency: float, high_stopping_frequency: float,
                 low_stopping_frequency: float, high_discharge_gradient: float, low_discharge_gradient: float,
                 high_charge_gradient: float, low_charge_gradient: float, high_return_gradient: float,
                 low_return_gradient: float, ramp_params: dict = None, use_julia: bool = False, **kwargs):
        super(FrequencyWatt, self).__init__(**kwargs)
        self.use_curves: bool = use_curves
        self.frequency_watt_curve: VertexCurve = VertexCurve(frequency_watt_curve)
        self.low_hysteresis_curve: VertexCurve = VertexCurve(low_hysteresis_curve)
        self.high_hysteresis_curve: VertexCurve = VertexCurve(high_hysteresis_curve)
        self.start_delay: Union[timedelta, float] = start_delay
        self.stop_delay: Union[timedelta, float] = stop_delay
        self.minimum_soc: float = minimum_soc
        self.maximum_soc: float = maximum_soc
        self.use_hysteresis: bool = use_hysteresis
        self.use_snapshot_power: bool = use_snapshot_power
        self.high_starting_frequency: float = high_starting_frequency
        self.low_starting_frequency: float = low_starting_frequency
        self.high_stopping_frequency: float = high_stopping_frequency
        self.low_stopping_frequency: float = low_stopping_frequency
        self.high_discharge_gradient: float = high_discharge_gradient
        self.low_discharge_gradient: float = low_discharge_gradient
        self.high_charge_gradient: float = high_charge_gradient
        self.low_charge_gradient: float = low_charge_gradient
        self.high_return_gradient: float = high_return_gradient
        self.low_return_gradient: float = low_return_gradient
        self.ramp_params: RampParams = RampParams(**(ramp_params or {}))
        self.use_julia: bool = use_julia
        # Hysteresis latch: whether the mode is currently actively responding.
        self._active: bool = False

    def control(self, schedule_period, start_time, sp_progress):
        if self.use_julia:
            return self._julia_control(schedule_period, start_time, sp_progress)

        frequency_response = next((c for c in self.use_cases if isinstance(c, FrequencyResponse)), None)
        if frequency_response is None:
            _log.error('Frequency-Watt mode requires a FrequencyResponse use case for the metered frequency input.')
            return 0.0

        frequency = frequency_response.metered_frequency
        # Hysteresis: start responding outside the starting thresholds; stop once the
        # frequency returns within the (narrower) stopping thresholds.
        if frequency >= self.high_starting_frequency or frequency <= self.low_starting_frequency:
            self._active = True
        elif self.low_stopping_frequency <= frequency <= self.high_stopping_frequency:
            self._active = False

        if not self._active:
            target_power = 0.0
        else:
            # Curve yields percent of maximum power for the measured frequency.
            watt_percentage = self.frequency_watt_curve.interpolate(frequency)
            target_power = watt_percentage / 100 * self.ess.maximum_power

        current_power = self.wip[-1]
        ramp_limited_power = self.ramp_params.apply_ramps(self.ess, current_power, target_power)
        energy_limited_power = self.controller.apply_energy_limits(
            ramp_limited_power, self.controller.resolution, self.minimum_soc, self.maximum_soc)
        _log.debug(f'FrequencyWatt: f={frequency}, active={self._active}, target={target_power},'
                   f' out={energy_limited_power}')
        return energy_limited_power

    def _get_julia_mode_struct(self):
        from julia.api import LibJulia
        api = LibJulia.load(julia='/home/volttron/PyJuliaTesting/julia-1.10.4/bin/julia')
        api.init_julia(['--project=/home/volttron/PyJuliaTesting/ctrl-eval-engine-app'])
        from julia.CtrlEvalEngine.EnergyStorageRTControl import (FrequencyWattMode, MesaModeParams, Vertex,
                                                                 RampParams as JuliaRampParams)
        from julia.CtrlEvalEngine.EnergyStorageRTControl import VertexCurve as JuliaVertexCurve
        mesa_mode_params = MesaModeParams(self.priority)
        ramp_params = JuliaRampParams(1000.0, 1000.0, 1000.0, 1000.0)

        def to_julia_curve(curve):
            return JuliaVertexCurve([Vertex(v.x, v.y) for v in curve.vertices])

        return FrequencyWattMode(mesa_mode_params, self.use_curves, to_julia_curve(self.frequency_watt_curve),
                                 to_julia_curve(self.low_hysteresis_curve), to_julia_curve(self.high_hysteresis_curve),
                                 self.start_delay, self.stop_delay, ramp_params, self.minimum_soc, self.maximum_soc,
                                 self.use_hysteresis, self.use_snapshot_power, self.high_starting_frequency,
                                 self.low_starting_frequency, self.high_stopping_frequency, self.low_stopping_frequency,
                                 self.high_discharge_gradient, self.low_discharge_gradient, self.high_charge_gradient,
                                 self.low_charge_gradient, self.high_return_gradient, self.low_return_gradient)
