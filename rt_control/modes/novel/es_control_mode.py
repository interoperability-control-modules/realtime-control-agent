import abc
import julia
import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ControlMode
from rt_control.util import FixedIntervalTimeSeries

setup_logging()
_log = logging.getLogger(__name__)

class ESControlMode(ControlMode):
    def __init__(self, ctrl_eval_engine_app_path: str, julia_path: str = '/usr/bin/julia', *args, **kwargs):
        super(ESControlMode, self).__init__(*args, **kwargs)
        from julia.api import LibJulia
        api = LibJulia.load(julia=julia_path)
        api.init_julia([f'--project={ctrl_eval_engine_app_path}'])
        from julia import Dates
        self.julia_dates = Dates
        from julia import CtrlEvalEngine
        self.CEE = CtrlEvalEngine

    def control(self, schedule_period, start_time, sp_progress) -> FixedIntervalTimeSeries:
        # TODO: Should this really be the start_time? Should it be created on each control call?
        sp_progress = self.CEE.VariableIntervalTimeSeries([start_time], []) # TODO: Should this be an instance variable?
        es_sims = self.CEE.EnergyStorageSimulators
        ess = es_sims.MockSimulator(es_sims.MockES_Specs(*self.ess.specs.dump()),
                                    es_sims.MockES_States(*self.ess.states.dump()))
        mode = self._get_julia_mode_struct()
        schedule_period = self.CEE.SchedulePeriod(*schedule_period.dump())
        use_cases = [u.to_julia() for u in self.use_cases] # TODO: If this is empty, pyjulia will make it a simple list.
                                                           #  Probably need to make a ScheduleFollowing UseCase
                                                           #  or a control function without the use_cases parameter.

        # TODO: Move this to agent with conditional import?
        controller = self.CEE.EnergyStorageRTControl.MesaController([mode], self.julia_dates.Minute(5))
        # TODO: Should this be calling the controller or mode control function?
        output = self.CEE.control(ess, controller, schedule_period, use_cases, start_time, sp_progress)
        return output.value[0]  # TODO: Is there really a use for returning a FixedIntervalTimeSeries as in ESControl?

    @abc.abstractmethod
    def _get_julia_mode_struct(self):
        pass


