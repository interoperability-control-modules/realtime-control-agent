import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging
from rt_control.ess import EnergyStorageSystem

setup_logging()
_log = logging.getLogger(__name__)


class FakeESS(EnergyStorageSystem):
    def __init__(self, controller, config):
        super(FakeESS, self).__init__(controller, config)
        # A fake storage has nothing publishing its state: seed it from the configuration (percent, kW).
        self.states.soc = float(config.get('initial_soc', 50.0))
        self.states.power = self.states.power_command = float(config.get('initial_power_kw', 0.0)) * 1000

    @EnergyStorageSystem.power_command.setter
    def power_command(self, value: float):
        _log.debug(f'Actuating command of: {value}')
        # Store the power command as the power and power_command (adjusting for unit).
        self.states.power = value * 1000
        self.states.power_command = value * 1000

    @EnergyStorageSystem.reactive_power_command.setter
    def reactive_power_command(self, value: float):
        _log.debug(f'Actuating reactive command of: {value}')
        # Store the reactive-power command locally (adjusting for unit) instead of RPCing.
        self.states.reactive_power = value * 1000
        self.states.reactive_power_command = value * 1000
