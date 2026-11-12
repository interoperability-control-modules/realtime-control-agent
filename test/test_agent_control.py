"""
Exercise the agent's control path (engine-backed modes combined by the Julia MESA controller, run-time parameter
changes, status) without a VOLTTRON platform.

    CEE_APP_PATH=/path/to/ctrl-eval-engine/app JULIA=/path/to/julia python test/test_agent_control.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from rt_control.agent import RTControlAgent
from rt_control.ess.fake_ess import FakeESS
from rt_control.modes import ControlMode
from rt_control.util import SchedulePeriod, VariableIntervalTimeSeries

APP_PATH = os.environ.get('CEE_APP_PATH',
                          os.path.join(os.path.dirname(__file__), '..', '..', 'ctrl-eval-engine', 'app'))
JULIA = os.environ.get('JULIA', 'julia')


class Harness:
    """The agent's control-path methods on a plain object (no VIP connection)."""
    _build_julia_controller = RTControlAgent._build_julia_controller
    on_mode_changed = RTControlAgent.on_mode_changed
    _mode = RTControlAgent._mode
    julia_modes = RTControlAgent.julia_modes
    control = RTControlAgent.control
    apply_energy_limits = RTControlAgent.apply_energy_limits
    set_mode_parameter = RTControlAgent.set_mode_parameter
    get_mode_parameters = RTControlAgent.get_mode_parameters
    get_point_map = RTControlAgent.get_point_map
    get_status = RTControlAgent.get_status
    list_modes = RTControlAgent.list_modes
    disable_mode = RTControlAgent.disable_mode
    enable_mode = RTControlAgent.enable_mode
    ingest_hub = RTControlAgent.ingest_hub
    apply_hub_values = RTControlAgent.apply_hub_values
    reset_hub_memory = RTControlAgent.reset_hub_memory
    _entry_in_effect = staticmethod(RTControlAgent._entry_in_effect)
    _apply_point = staticmethod(RTControlAgent._apply_point)
    hub_status = RTControlAgent.hub_status
    hub_modes = RTControlAgent.hub_modes

    class core:
        identity = 'rtc'

    def __init__(self):
        self.resolution = timedelta(seconds=1)
        self.cee_app_path = APP_PATH
        self.julia_path = JULIA
        self.use_cases = []
        self.modes = []
        self.controller_config = {'SocUseMinPct': 10, 'SocUseMaxPct': 90,
                                  'maxRampRates': {'RpuRteMax': 50, 'RpdRteMax': 50}}
        self.julia_controller = None
        self.wip = []
        self.hub_topic = 'rtc/control'
        self._hub_last = {}


harness = Harness()
ess = FakeESS(harness, {'power_capacity_kw': 100.0, 'energy_capacity_kwh': 125.0})
ess.states.soc = 50.0
harness.ess = ess

configs = [
    {'name': 'schedule', 'class_name': 'ChargeDischargeStorage', 'priority': 2,
     'active_power_target_percent': 50.0, 'RpuRte': 10, 'RpdRte': 10, 'RpuChaRte': 10, 'RpdChaRte': 10},
    {'name': 'limit', 'class_name': 'ActivePowerLimit', 'priority': 0, 'maximum_percent': 30.0},
    {'name': 'peak', 'class_name': 'PeakPowerLimiting', 'priority': 1, 'activation_threshold': 1000.0},
]
for cfg in configs:
    cfg = dict(cfg)
    cfg['ctrl_eval_engine_app_path'] = APP_PATH
    cfg['julia_path'] = JULIA
    mode = ControlMode.factory(harness, ess, harness.use_cases, RTControlAgent.mode_config(cfg, 'engine'))
    mode.name = cfg.get('name', type(mode).__name__)
    harness.modes.append(mode)
harness.modes.sort(key=lambda m: m.priority)
harness._build_julia_controller()
assert harness.julia_controller is not None

point_map = harness.get_point_map()
assert point_map['limit']['DWMX.LimW'] == 'LimWMax' and point_map['limit']['DWMN.LimW'] == 'LimWMin', point_map
assert point_map['schedule']['DWGC.GnWPctSpt'] == 'GnWPctSpt'
assert harness.get_mode_parameters('schedule')['GnWPctSpt'] == 50.0


def run(ticks, t0):
    outputs = []
    t = t0
    for _ in range(ticks):
        command = harness.control(SchedulePeriod(0.0, t0, duration=timedelta(hours=1)), t, VariableIntervalTimeSeries())
        ess.power_command = command[0]        # the fake ESS reports the command back as its power
        outputs.append(command[0])
        t += harness.resolution
    return outputs


t0 = datetime(2024, 8, 21, 12, 0, tzinfo=timezone.utc)
# 10 %/s of 100 kW ramps 10 kW per second toward 50 kW; the 30 % limit caps at 30 kW.
outputs = run(5, t0)
assert outputs == [10.0, 20.0, 30.0, 30.0, 30.0], outputs
status = harness.get_status()
assert status['base_mode'] == 'schedule' and status['binding']['bounds'], status
assert status['modes']['limit']['active'] and not status['modes']['peak']['active'], status

# Raise the limit at run time: the mode is rebuilt and swapped into the controller without losing its state.
harness.set_mode_parameter('limit', 'maximum_percent', 60.0)
outputs = run(3, t0 + timedelta(seconds=5))
assert outputs == [40.0, 50.0, 50.0], outputs

# Disable the schedule-following mode: the base falls back to the schedule period's power (0 kW); only the device
# maximum ramp (50 %/s) applies, so the output drops within one step. Re-enabling ramps up again at the mode's 10 kW/s.
harness.disable_mode('schedule')
outputs = run(2, t0 + timedelta(seconds=8))
assert outputs == [0.0, 0.0], outputs
assert harness.get_status()['modes']['schedule']['enabled'] is False
harness.enable_mode('schedule')
outputs = run(2, t0 + timedelta(seconds=10))
assert outputs == [10.0, 20.0], outputs

# Hub format: a sub-topic is one controlling source; its republished, unchanged state is not re-applied, so another
# source's newer command stands. The base topic carries commands and always applies.
harness.ingest_hub(None, 'da', 'pubsub', 'rtc/control/dnp3', {}, [{'DWMX': {'LimW': 40.0, 'ModEna': True}}])
assert harness.get_mode_parameters('limit')['LimWMax'] == 40.0
harness.ingest_hub(None, 'da', 'pubsub', 'rtc/control/sunspec', {}, [{'DWMX': {'LimW': 70.0}}])
assert harness.get_mode_parameters('limit')['LimWMax'] == 70.0
harness.ingest_hub(None, 'da', 'pubsub', 'rtc/control/dnp3', {}, [{'DWMX': {'LimW': 40.0, 'ModEna': True}}])
assert harness.get_mode_parameters('limit')['LimWMax'] == 70.0, 'a source re-asserting its old value must not win'
harness.ingest_hub(None, 'op', 'pubsub', 'rtc/control', {}, json.dumps({'DWMX': {'LimW': 100, 'ModEna': False}}))
assert harness.get_mode_parameters('limit')['LimWMax'] == 100 and harness.get_mode_parameters('limit')['ModEna'] is False
harness.ingest_hub(None, 'da', 'pubsub', 'rtc/control/sunspec', {}, [{'DWMX': {'LimW': 70.0}}])
assert harness.get_mode_parameters('limit')['LimWMax'] == 100, 'unchanged device state must not undo the command'
harness.ingest_hub(None, 'op', 'pubsub', 'rtc/control', {}, json.dumps({'DWMX': {'LimW': 100, 'ModEna': False}}))
harness.ingest_hub(None, 'op', 'pubsub', 'rtc/control', {}, json.dumps({'DWMX': {'LimW': 55, 'ModEna': True}}))
assert harness.get_mode_parameters('limit')['LimWMax'] == 55, 'base-topic commands always apply'
harness.ingest_hub(None, 'rtc', 'pubsub', 'rtc/control', {'origin': 'rtc'}, [{'DWMX': {'LimW': 1}}])
assert harness.get_mode_parameters('limit')['LimWMax'] == 55, 'the agent ignores its own publications'
modes = harness.hub_modes()
assert modes['DWMX']['LimW'] == 55 and modes['DWMX']['ModEna'] is True, modes
assert 'TotW' in harness.hub_status(include_modes=False)['DECP']['MMXU'], harness.hub_status()

print('agent control path through the Julia MESA controller OK')
