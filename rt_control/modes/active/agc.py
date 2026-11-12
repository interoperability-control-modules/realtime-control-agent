import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import MesaMode, RampParams
from rt_control.use_cases.regulation import Regulation

setup_logging()
_log = logging.getLogger(__name__)


class AGC(MesaMode):
    # Native Python port of the ctrl-eval-engine MESA AGCMode (mesa-agc-mode.jl).
    # Follows an AGC regulation signal scaled by the scheduled regulation capacity.
    # Set use_julia=True to fall back to the pyjulia-wrapped implementation.
    def __init__(self, minimum_usable_soc: float, maximum_usable_soc: float,
                 ramp_or_time_constant: bool = True, ramp_params: dict = None,
                 use_julia: bool = False, **kwargs):
        super(AGC, self).__init__(**kwargs)
        self.minimum_usable_soc: float = minimum_usable_soc
        self.maximum_usable_soc: float = maximum_usable_soc
        self.ramp_or_time_constant: bool = ramp_or_time_constant
        self.ramp_params: RampParams = RampParams(**(ramp_params or {}))
        self.use_julia: bool = use_julia

    def control(self, schedule_period, start_time, sp_progress):
        if self.use_julia:
            return self._julia_control(schedule_period, start_time, sp_progress)

        regulation = next((c for c in self.use_cases if isinstance(c, Regulation)), None)
        if regulation is None:
            # No Regulation use case: follow the schedule power, clamped to ESS limits.
            scheduled_power = schedule_period.p
            return min(max(scheduled_power, self.ess.minimum_power), self.ess.maximum_power)

        # AGC signal is per-unit; scale by the scheduled regulation capacity (kW).
        agc_signal_pu = regulation.agc_signal
        active_power_target = schedule_period.reg_cap_kw * agc_signal_pu

        # Move towards the target as appropriate to ramp-rate or time-constant limits.
        current_power = self.wip[-1]
        if self.ramp_or_time_constant:
            ramp_limited_power = self.ramp_params.apply_ramps(self.ess, current_power, active_power_target)
        else:
            ramp_limited_power = self.ramp_params.apply_time_constants(current_power, active_power_target)

        # Apply mode-specific energy limits using the usable SOC band.
        energy_limited_power = self.controller.apply_energy_limits(
            ramp_limited_power, self.controller.resolution,
            self.minimum_usable_soc, self.maximum_usable_soc)
        _log.debug(f'AGC: agc_pu={agc_signal_pu}, target={active_power_target}, output={energy_limited_power}')
        return energy_limited_power

    def _get_julia_mode_struct(self):
        from julia.api import LibJulia
        api = LibJulia.load(julia='/home/volttron/PyJuliaTesting/julia-1.10.4/bin/julia')
        api.init_julia(['--project=/home/volttron/PyJuliaTesting/ctrl-eval-engine-app'])
        from julia.CtrlEvalEngine.EnergyStorageRTControl import (AGCMode, MesaModeParams,
                                                                 RampParams as JuliaRampParams)
        mesa_mode_params = MesaModeParams(self.priority)
        ramp_params = JuliaRampParams(1000.0, 1000.0, 1000.0, 1000.0)
        return AGCMode(mesa_mode_params, True, ramp_params, self.minimum_usable_soc, self.maximum_usable_soc)
