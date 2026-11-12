import logging

from datetime import timedelta
from typing import Union

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import MesaMode, RampParams
from rt_control.use_cases.generation_following import GenerationFollowing
from rt_control.use_cases.load_following import LoadFollowing

setup_logging()
_log = logging.getLogger(__name__)


class ActivePowerSmoothing(MesaMode):
    # Native implementation of the MESA Active Power Smoothing mode. The Julia
    # ctrl-eval-engine mode body is an unimplemented stub, so this is derived from the
    # MESA-ESS spec: the ESS counteracts rapid variation in a reference power signal by
    # outputting the negative rate-of-change scaled by a smoothing gradient, bounded by
    # lower/upper smoothing limits (percent of maximum power). Set use_julia=True to
    # fall back to the (stub) pyjulia implementation.
    def __init__(self, smoothing_gradient: float, lower_smoothing_limit: float, upper_smoothing_limit: float,
                 smoothing_filter_time: Union[float, timedelta], ramp_params: dict = None,
                 use_julia: bool = False, **kwargs):
        super(ActivePowerSmoothing, self).__init__(**kwargs)
        self.smoothing_gradient: float = smoothing_gradient
        self.lower_smoothing_limit: float = lower_smoothing_limit
        self.upper_smoothing_limit: float = upper_smoothing_limit
        self.smoothing_filter_time: timedelta = timedelta(seconds=smoothing_filter_time) \
            if not isinstance(smoothing_filter_time, timedelta) else smoothing_filter_time
        self.ramp_params: RampParams = RampParams(**(ramp_params or {}))
        self.use_julia: bool = use_julia
        # Previous reference-power sample, for rate-of-change estimation.
        self._previous_reference_power: float = 0.0

    def _reference_power(self):
        # Smooth whichever generation/load reference is configured as a use case.
        gen_following = next((c for c in self.use_cases if isinstance(c, GenerationFollowing)), None)
        if gen_following is not None:
            return gen_following.realtime_power
        load_following = next((c for c in self.use_cases if isinstance(c, LoadFollowing)), None)
        if load_following is not None:
            return load_following.realtime_power
        return 0.0

    def control(self, schedule_period, start_time, sp_progress):
        if self.use_julia:
            return self._julia_control(schedule_period, start_time, sp_progress)

        reference_power = self._reference_power()
        resolution_seconds = self.controller.resolution.seconds or 1
        # Rate of change of the reference (kW/s); oppose it, scaled by the gradient.
        rate_of_change = (reference_power - self._previous_reference_power) / resolution_seconds
        self._previous_reference_power = reference_power
        target_power = -self.smoothing_gradient * rate_of_change

        # Bound by the smoothing limits (percent of maximum power).
        lower_bound = self.lower_smoothing_limit / 100 * self.ess.maximum_power
        upper_bound = self.upper_smoothing_limit / 100 * self.ess.maximum_power
        target_power = min(max(target_power, lower_bound), upper_bound)

        current_power = self.wip[-1]
        ramp_limited_power = self.ramp_params.apply_ramps(self.ess, current_power, target_power)
        energy_limited_power = self.controller.apply_energy_limits(ramp_limited_power, self.controller.resolution)
        _log.debug(f'ActivePowerSmoothing: dP/dt={rate_of_change}, target={target_power}, out={energy_limited_power}')
        return energy_limited_power

    def _get_julia_mode_struct(self):
        from julia.api import LibJulia
        api = LibJulia.load(julia='/home/volttron/PyJuliaTesting/julia-1.10.4/bin/julia')
        api.init_julia(['--project=/home/volttron/PyJuliaTesting/ctrl-eval-engine-app'])
        from julia.CtrlEvalEngine.EnergyStorageRTControl import (ActivePowerSmoothingMode, MesaModeParams,
                                                                 RampParams as JuliaRampParams)
        mesa_mode_params = MesaModeParams(self.priority)
        ramp_params = JuliaRampParams(1000.0, 1000.0, 1000.0, 1000.0)
        return ActivePowerSmoothingMode(mesa_mode_params, self.smoothing_gradient, self.lower_smoothing_limit,
                                        self.upper_smoothing_limit, self.smoothing_filter_time, ramp_params)
