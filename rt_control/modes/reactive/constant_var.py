import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ReactiveMesaMode

setup_logging()
_log = logging.getLogger(__name__)


class ConstantVar(ReactiveMesaMode):
    """MESA Constant VArs mode: command a fixed reactive-power target expressed as a
    percentage of the ESS maximum reactive power (DNP3 VArTgt, positive = capacitive /
    injecting VARs, negative = inductive / absorbing). New native implementation; the
    Julia ctrl-eval-engine has no reactive modes, so there is no fallback.
    """
    def __init__(self, reactive_power_target: float, **kwargs):
        super(ConstantVar, self).__init__(**kwargs)
        self.reactive_power_target: float = reactive_power_target  # Percent of maximum reactive power.

    def control_reactive(self, schedule_period, start_time, sp_progress):
        target = self.reactive_power_target / 100 * self.ess.maximum_reactive_power
        _log.debug(f'ConstantVar: target {self.reactive_power_target}% -> {target} kVAR')
        return target
