import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import MesaMode

setup_logging()
_log = logging.getLogger(__name__)


class ActivePowerLimit(MesaMode):
    # Native Python port of the ctrl-eval-engine MESA ActivePowerLimitMode
    # (mesa-active-power-limit-mode.jl). Constrains power to configured charge/discharge
    # percentage limits and returns the delta needed to bring the running sum within them.
    # Set use_julia=True to fall back to the pyjulia-wrapped implementation.
    def __init__(self, maximum_charge_percentage: float, maximum_discharge_percentage: float,
                 use_julia: bool = False, **kwargs):
        super(ActivePowerLimit, self).__init__(**kwargs)
        self.maximum_charge_percentage: float = maximum_charge_percentage
        self.maximum_discharge_percentage: float = maximum_discharge_percentage
        self.use_julia: bool = use_julia

    def control(self, schedule_period, start_time, sp_progress):
        if self.use_julia:
            return self._julia_control(schedule_period, start_time, sp_progress)

        # NOTE: The Julia mode receives the controller's running iteration sum. The native
        # control() signature does not, so we clamp against this mode's own last value
        # (self.wip[-1]) and return the correcting delta, mirroring the Julia
        # `constrainedPower - currentIterationPower`. When used as the sole/last mode this
        # matches; combined-mode limiting is a documented follow-up.
        current_iteration_power = self.wip[-1]
        max_allowed_charge_power = self.maximum_charge_percentage / 100 * self.ess.minimum_power
        max_allowed_discharge_power = self.maximum_discharge_percentage / 100 * self.ess.maximum_power
        constrained_power = max(min(current_iteration_power, max_allowed_discharge_power), max_allowed_charge_power)
        _log.debug(f'ActivePowerLimit: current={current_iteration_power}, constrained={constrained_power}')
        return constrained_power - current_iteration_power

    def _get_julia_mode_struct(self):
        from julia.api import LibJulia
        api = LibJulia.load(julia='/home/volttron/PyJuliaTesting/julia-1.10.4/bin/julia')
        api.init_julia(['--project=/home/volttron/PyJuliaTesting/ctrl-eval-engine-app'])
        from julia.CtrlEvalEngine.EnergyStorageRTControl import ActivePowerLimitMode, MesaModeParams
        mesa_mode_params = MesaModeParams(self.priority)
        return ActivePowerLimitMode(mesa_mode_params, self.maximum_charge_percentage, self.maximum_discharge_percentage)
