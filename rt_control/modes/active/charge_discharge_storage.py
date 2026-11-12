import logging

from typing import Union

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import MesaMode, RampParams

setup_logging()
_log = logging.getLogger(__name__)


class ChargeDischargeStorage(MesaMode):
    # Native Python port of the ctrl-eval-engine MESA ChargeDischargeStorageMode
    # (mesa-charge-discharge-storage-mode.jl). Set use_julia=True to fall back to
    # the pyjulia-wrapped implementation instead.
    def __init__(self, minimum_reserve_percent: float = 10.0, maximum_reserve_percent: float = 90.0,
                 active_power_target: Union[float, None] = None, ramp_or_time_constant: bool = True,
                 ramp_params: dict = None, use_julia: bool = False, **kwargs):
        super(ChargeDischargeStorage, self).__init__(**kwargs)
        self.minimum_reserve_percent: float = minimum_reserve_percent
        self.maximum_reserve_percent: float = maximum_reserve_percent
        # None for the target enables schedule following.
        self.active_power_target: Union[float, None] = active_power_target
        # True selects ramp-rate limiting, False selects time-constant limiting.
        self.ramp_or_time_constant: bool = ramp_or_time_constant
        # Defaults match the Julia RampParams(1000, 1000, 1000, 1000) -> full p_max/p_min per step.
        self.ramp_params: RampParams = RampParams(**(ramp_params or {}))
        self.use_julia: bool = use_julia

    def control(self, schedule_period, start_time, sp_progress):
        if self.use_julia:
            return self._julia_control(schedule_period, start_time, sp_progress)

        # Use the specified target percentage if it exists, otherwise follow the SchedulePeriod power.
        if self.active_power_target is not None:
            active_power_target = self.active_power_target
        elif self.ess.maximum_power:
            active_power_target = schedule_period.p / self.ess.maximum_power * 100
        else:
            active_power_target = 0.0

        # Constrain the target percentage by storage power limits.
        # TODO: ess.minimum_power currently returns 0.0, so negative (charge) targets collapse to 0.
        if active_power_target >= 0:
            target_power = active_power_target * self.ess.maximum_power / 100
        else:
            target_power = -active_power_target * self.ess.minimum_power / 100

        # Move towards the target power as appropriate to ramp-rate or time-constant limits.
        current_power = self.wip[-1]
        if self.ramp_or_time_constant:
            ramp_limited_power = self.ramp_params.apply_ramps(self.ess, current_power, target_power)
        else:
            ramp_limited_power = self.ramp_params.apply_time_constants(current_power, target_power)

        # Apply mode-specific energy (reserve) limits.
        energy_limited_power = self.controller.apply_energy_limits(
            ramp_limited_power, self.controller.resolution,
            self.minimum_reserve_percent, self.maximum_reserve_percent)
        _log.debug(f'ChargeDischargeStorage: target_power={target_power}, ramp_limited={ramp_limited_power},'
                   f' energy_limited={energy_limited_power}')
        return energy_limited_power

    def _get_julia_mode_struct(self):
        from julia.api import LibJulia
        api = LibJulia.load(julia='/home/volttron/PyJuliaTesting/julia-1.10.4/bin/julia')
        api.init_julia(['--project=/home/volttron/PyJuliaTesting/ctrl-eval-engine-app'])
        from julia.CtrlEvalEngine.EnergyStorageRTControl import (ChargeDischargeStorageMode, MesaModeParams,
                                                                 RampParams as JuliaRampParams)
        # The only required parameter is the priority.
        mesa_mode_params = MesaModeParams(self.priority)
        # Ramp will be the p_max if the values are 1000.0.
        ramp_params = JuliaRampParams(1000.0, 1000.0, 1000.0, 1000.0)
        # The mode will follow the schedule if None is passed for the target value.
        return ChargeDischargeStorageMode(mesa_mode_params, True, ramp_params, self.minimum_reserve_percent,
                                          self.maximum_reserve_percent, self.active_power_target)
