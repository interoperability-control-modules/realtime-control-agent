import json
import logging
import sys

from datetime import datetime, timedelta

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
    from volttron.client.vip.agent import Agent, Core, RPC
    from volttron.utils import get_aware_utc_now, load_config, parse_timestamp_string, vip_main
    from volttron.utils.scheduling import periodic
except PackageNotFoundError:
    from volttron.platform.agent.utils import (get_aware_utc_now, load_config, parse_timestamp_string, setup_logging,
                                               vip_main)
    from volttron.platform.scheduling import periodic
    from volttron.platform.vip.agent import Agent, Core, RPC

from rt_control.ess import EnergyStorageSystem
from rt_control.modes import ControlMode, EmergencyMesaMode, ReactiveMesaMode
from rt_control.modes.engine.es_control_mode import ESControlMode, coerce_scalar
from rt_control.use_cases import UseCase
from rt_control.util import FixedIntervalTimeSeries, SchedulePeriod, VariableIntervalTimeSeries, camel_to_snake

setup_logging()
_log = logging.getLogger(__name__)

__version__ = '0.3'

HUB_FORMAT = 'rtc_controller'       # the presentation service format the agent speaks: plain copies of the 61850 hub's LNs
HEADER_FORMAT = 'format'
HEADER_ORIGIN = 'origin'


class RTControlAgent(Agent):
    """Real-time controller of one energy storage system.

    Modes backed by the CtrlEvalEngine (`ESControlMode`) are combined by one Julia `MesaController` per IEEE 1815.2
    (replacing / additive / bounding, priorities, timing parameters, response limiting); the `controller` section of
    the configuration carries its settings (`SocUseMinPct`, `SocUseMaxPct`, `maxRampRates`, `OpnLoopTau`, `OplPct`).
    Python-only modes are still summed onto that result, which is the legacy behaviour and not standard-conformant;
    prefer the Julia-backed modes.
    """

    def __init__(self, config_path, *args, **kwargs):
        super(RTControlAgent, self).__init__(*args, **kwargs)
        config = load_config(config_path)
        self.vip.config.set_default('config', config)

        self.ess: EnergyStorageSystem = EnergyStorageSystem.factory(self, {})
        self.modes: list[ControlMode] = []
        self.resolution: timedelta = timedelta(seconds=1.0)
        self.schedule: list[SchedulePeriod] = []
        self.schedule_topic = None
        self.use_cases: list[UseCase] = []
        self.wip: FixedIntervalTimeSeries = FixedIntervalTimeSeries(get_aware_utc_now(), self.resolution)
        self.controller_config: dict = {}
        self.julia_controller = None
        self.last_control_time: datetime = None
        self._last_reactive_command: float = 0.0
        self._has_reactive_modes: bool = False

        self.cee_app_path: str = None
        self.julia_path: str = None

        self._loop = None
        self._stop = False

        self.vip.config.subscribe(self.configure_main, ['NEW', 'UPDATE'], 'config')

    # ------------------------------------------------------------------ configuration
    def configure_main(self, _, __, contents):
        self.ess = EnergyStorageSystem.factory(self, dict(contents.get('ess', {})))
        self.resolution = timedelta(seconds=contents.get('resolution', self.resolution.total_seconds()))
        self.wip = FixedIntervalTimeSeries(get_aware_utc_now(), self.resolution)
        time_string = contents.get('start_time')
        self.wip.start_time = parse_timestamp_string(time_string) if time_string else get_aware_utc_now()
        self.schedule_topic = contents.get('schedule_topic')
        self.hub_topic = contents.get('hub_topic')              # a prefix: one sub-topic per controlling source is expected
        self.status_topic = contents.get('status_topic')        # measurements (DECP.MMXU, DSTO), and the modes unless ...
        self.modes_topic = contents.get('modes_topic')          # ... a separate topic carries the modes' parameters and read-backs
        self._hub_last = {}                                     # per source topic: the LN.DO values last applied from it
        self.julia_path = contents.get('julia_path')
        self.cee_app_path = contents.get('ctrl_eval_engine_app_path')
        self.controller_config = contents.get('controller', {})
        self.schedule = [SchedulePeriod(**s) for s in contents.get('schedule', [])]

        # Factories pop keys from the dictionaries they are given, so hand them copies.
        self.use_cases = [UseCase.factory(self, dict(u)) for u in contents.get('use_cases', [])]
        self.modes = []
        package = contents.get('mode_package')      # e.g. "engine": the modes subpackage a class_name selects from
        for m in contents.get('modes', []):
            mode = ControlMode.factory(self, self.ess, self.use_cases, self.mode_config(m, package))
            mode.name = m.get('name', m.get('class_name'))
            self.modes.append(mode)
        self.modes.sort(key=lambda md: md.priority)
        self._build_julia_controller()

        if self.schedule_topic:
            self.vip.pubsub.subscribe('pubsub', self.schedule_topic, self.ingest_schedule)
        if self.hub_topic:
            self.vip.pubsub.subscribe('pubsub', self.hub_topic, self.ingest_hub)
        if self._loop is not None:
            self._loop.cancel()
        self._loop = self.core.schedule(periodic(self.resolution.total_seconds()), self.loop)

    @staticmethod
    def mode_config(config: dict, package: str = None) -> dict:
        """A copy of a mode's configuration for the factory. With `package`, a mode without an explicit `module_name`
        is taken from that subpackage of `rt_control.modes` (the engine-backed and the native MESA modes share
        class names)."""
        cfg = dict(config)
        if package and 'module_name' not in cfg:
            cfg['module_name'] = f'rt_control.modes.{package}.{camel_to_snake(cfg["class_name"])}'
        return cfg

    def julia_modes(self) -> list[ESControlMode]:
        return [m for m in self.modes if isinstance(m, ESControlMode)]

    def _build_julia_controller(self):
        julia_modes = self.julia_modes()
        if not julia_modes:
            self.julia_controller = None
            return
        rt = julia_modes[0].runtime
        cfg = self.controller_config
        kwargs = {k: float(cfg[k]) for k in ('SocUseMinPct', 'SocUseMaxPct', 'OplPct') if k in cfg}
        if 'OpnLoopTau' in cfg:
            kwargs['OpnLoopTau'] = bool(cfg['OpnLoopTau'])
        if 'randomSeed' in cfg and cfg['randomSeed'] is not None:
            kwargs['randomSeed'] = int(cfg['randomSeed'])
        max_rates = cfg.get('maxRampRates')
        if max_rates:
            kwargs['maxRampRates'] = rt.ES.RampParams(
                RpuRte=max_rates.get('RpuRteMax'), RpdRte=max_rates.get('RpdRteMax'),
                RpuChaRte=max_rates.get('RpuChaRteMax'), RpdChaRte=max_rates.get('RpdChaRteMax'))
        self.julia_controller = rt.ES.MesaController([m.julia_mode for m in julia_modes], rt.millis(self.resolution),
                                                     **kwargs)
        _log.info(f'Built MESA controller with modes: {[m.name for m in julia_modes]}')

    def on_mode_changed(self, mode: ESControlMode):
        """A mode rebuilt its Julia struct after a parameter change: swap it into the controller, keeping its state."""
        if self.julia_controller is None:
            return
        julia_modes = self.julia_modes()
        index = julia_modes.index(mode) + 1   # Julia is 1-based
        mode.runtime.ES.replace_mode_b(self.julia_controller, index, mode.julia_mode)

    def _mode(self, name: str) -> ControlMode:
        for mode in self.modes:
            if getattr(mode, 'name', None) == name or type(mode).__name__ == name:
                return mode
        raise KeyError(f'No mode named "{name}"; configured modes: {[getattr(m, "name", None) for m in self.modes]}')

    # ------------------------------------------------------------------ schedule
    def ingest_schedule(self, _, sender, __, topic, headers, message):
        now = get_aware_utc_now()
        for dt_string, period in message.items():
            dt = parse_timestamp_string(dt_string)
            set_point = period.get('bess_setpoint')
            duration = timedelta(seconds=period.get('duration_in_seconds', 3600))
            if dt is None or set_point is None:
                _log.warning(f'Unable to ingest published schedule on {topic} from {sender}'
                             f' for forecast_time: {dt}, message: {message}')
            else:
                self.schedule.append(SchedulePeriod(p=set_point, t_start=dt, duration=duration))
        self.schedule = [s for s in self.schedule if s.end_time > now]
        self.schedule.sort(key=lambda s: s.t_start)
        _log.info(f'Scheduling information received from subscription. Schedule is now: {self.schedule}')

    # ------------------------------------------------------------------ hub format (61850-shaped) in and out
    def ingest_hub(self, peer, sender, bus, topic, headers, message):
        """A message in the `rtc_controller` format (the hub's logical nodes) published by a Resource Bridge bus end:
        apply every data object a mode's point map knows to that mode."""
        if (headers or {}).get(HEADER_ORIGIN) == self.core.identity:
            return
        values = message[0] if isinstance(message, list) and message else message
        if isinstance(values, str):          # `vctl publish` and other text publishers send JSON text
            try:
                values = json.loads(values)
            except ValueError:
                _log.warning(f'Ignoring hub message on {topic} from {sender}: not JSON: {values[:80]!r}')
                return
        if not isinstance(values, dict):
            _log.warning(f'Ignoring hub message on {topic} from {sender}: not a mapping ({type(values).__name__})')
            return
        # Messages on the base topic are commands (an operator, a test), not a device's republished state: apply them
        # in full. Sub-topics belong to one source each and go through that source's change memory.
        source = None if topic == self.hub_topic else topic
        applied = self.apply_hub_values(values, source=source)
        _log.info(f'Applied hub message from {sender} on {topic}: {applied}')

    @staticmethod
    def _entry_in_effect(entry: dict, now: datetime) -> bool:
        start = entry.get('StrTm')
        if start is None:
            return True
        start = float(start)
        interval = entry.get('SchdIntv')
        t = now.timestamp()
        return start <= t and (interval is None or t < start + float(interval))

    @RPC.export
    def reset_hub_memory(self):
        """Forget what each source last asserted, so that the next message from any source is applied in full."""
        self._hub_last.clear()
        return True

    @RPC.export
    def apply_hub_values(self, values: dict, source: str = None) -> dict:
        """Apply a dict keyed by 61850 logical node (`{"DWMX": {"LimW": 50, "ModEna": true}, ...}`) to the modes.
        `FSCH.SchdEntr` entries in effect now are applied like immediate values (later starts win). With a `source`
        (the topic a Resource Bridge bus end publishes on), only values that differ from what that source last asserted
        are applied: devices republish their whole state every poll, and a stale limit from one controller must not
        undo a newer one from another. Returns the points applied as `{"LN.DO": value}`."""
        now = get_aware_utc_now()
        last = self._hub_last.setdefault(source, {}) if source is not None else None
        groups = {ln: dict(group) for ln, group in values.items() if isinstance(group, dict)}
        entries = (groups.pop('FSCH', {}) or {}).get('SchdEntr') or []
        for entry in sorted((e for e in entries if isinstance(e, dict) and self._entry_in_effect(e, now)),
                            key=lambda e: float(e.get('StrTm') or 0)):
            for ln, group in entry.items():
                if ln not in ('StrTm', 'SchdIntv') and isinstance(group, dict):
                    groups.setdefault(ln, {}).update(group)
        applied, touched = {}, []
        for ln, group in groups.items():
            for do, value in group.items():
                if isinstance(value, dict) and 'crvPts' not in value:
                    continue        # nested status groups (DECP.MMXU) are not mode parameters
                point = f'{ln}.{do}'
                if last is not None:
                    if point in last and last[point] == value:
                        continue
                    last[point] = value
                for mode in self.julia_modes():
                    field = mode.point_map().get(point)
                    if field is None:
                        continue
                    self._apply_point(mode, field, value)
                    applied[point] = value
                    if mode not in touched:
                        touched.append(mode)
        for mode in touched:
            mode.julia_mode = mode.build()
            self.on_mode_changed(mode)
        return applied

    @staticmethod
    def _apply_point(mode: ESControlMode, field: str, value):
        value = coerce_scalar(value)
        if field == 'ModEna':
            mode.shared['ModEna'] = bool(value)
        elif field == 'ModPrio':
            mode.priority = int(value)
        else:
            mode.set_parameter(field, value, rebuild=False)

    @RPC.export
    def hub_status(self, include_modes: bool = True) -> dict:
        """The agent's status in the `rtc_controller` format: the ESS's power and SOC under DECP.MMXU / DSTO and, with
        `include_modes`, every engine-backed mode's parameters and attempted output under its logical node."""
        # The hub spells state of charge three ways (SocPct, SocUsePct, UseSocPct); report all so every edge finds it.
        status = {'DECP': {'MMXU': {'TotW': round(self.ess.power * 1000, 3)}},
                  'DSTO': {'SocPct': self.ess.soc, 'SocUsePct': self.ess.soc, 'UseSocPct': self.ess.soc}}
        if include_modes:
            status.update(self.hub_modes())
        return status

    @RPC.export
    def hub_modes(self) -> dict:
        """Every engine-backed mode's parameters and attempted output under its logical node, in the hub format.
        On the hub a setpoint and its read-back share one name (DWMX.LimW), so these are published apart from the
        measurements: bridge them only to targets whose read-backs are distinct from their controls (a 1815.2 outstation's
        analog inputs), never to a device whose control points they would overwrite."""
        status = {}
        julia_modes = self.julia_modes()
        attempted = {}
        if self.julia_controller is not None and julia_modes:
            st = julia_modes[0].runtime.ES.mesa_status(self.julia_controller)
            attempted = {m.name: float(a) for m, a in zip(julia_modes, st.attempted)}
        for mode in julia_modes:
            params = mode.parameters()
            for point, field in mode.point_map().items():
                value = params.get(field)
                if value is None:
                    continue
                ln, do = point.split('.', 1)
                status.setdefault(ln, {})[do] = value
            if mode.REQ_FIELD and mode.name in attempted:
                status.setdefault(mode.LN, {})[mode.REQ_FIELD] = attempted[mode.name]
        return status

    def publish_status(self):
        headers = {'Content-Type': 'application/json', HEADER_FORMAT: HUB_FORMAT, HEADER_ORIGIN: self.core.identity}
        if self.status_topic:
            self.vip.pubsub.publish('pubsub', topic=self.status_topic, headers=headers,
                                    message=self.hub_status(include_modes=not self.modes_topic))
        if self.modes_topic:
            self.vip.pubsub.publish('pubsub', topic=self.modes_topic, headers=headers, message=self.hub_modes())

    # ------------------------------------------------------------------ RPC
    @RPC.export
    def list_modes(self):
        return [{'name': getattr(m, 'name', None), 'class_name': type(m).__name__, 'priority': m.priority,
                 'parameters': m.parameters() if isinstance(m, ESControlMode) else m.config}
                for m in self.modes]

    @RPC.export
    def enable_mode(self, name: str):
        mode = self._mode(name)
        if isinstance(mode, ESControlMode) and self.julia_controller is not None:
            rt = mode.runtime
            # The enable is stamped with the controller's current time so the enabling window starts now.
            t = getattr(self, 'last_control_time', None) or get_aware_utc_now()
            rt.ES.enable_b(self.julia_controller, mode.julia_mode, rt.datetime(t))
            mode.shared['ModEna'] = True
        return True

    @RPC.export
    def disable_mode(self, name: str):
        mode = self._mode(name)
        if isinstance(mode, ESControlMode) and self.julia_controller is not None:
            mode.runtime.ES.disable_b(self.julia_controller, mode.julia_mode)
            mode.shared['ModEna'] = False
        return True

    @RPC.export
    def set_mode_parameter(self, name: str, parameter: str, value):
        """Set one parameter by its 61850 name or readable alias; the Julia mode is rebuilt in place."""
        mode = self._mode(name)
        if not isinstance(mode, ESControlMode):
            raise TypeError(f'Mode "{name}" is not engine-backed; its parameters are fixed at configuration.')
        mode.set_parameter(parameter, value)
        return mode.parameters()

    @RPC.export
    def get_mode_parameters(self, name: str):
        mode = self._mode(name)
        return mode.parameters() if isinstance(mode, ESControlMode) else mode.config

    @RPC.export
    def get_point_map(self):
        """61850 point name -> (mode name, parameter) for every engine-backed mode."""
        return {m.name: m.point_map() for m in self.julia_modes()}

    @RPC.export
    def get_status(self):
        """The MESA controller's last tick: output, base, per-mode enabled/active/suppressed/attempted, bindings."""
        if self.julia_controller is None:
            return {'output_kw': self.wip[-1] if self.wip else None, 'modes': {}}
        julia_modes = self.julia_modes()
        st = julia_modes[0].runtime.ES.mesa_status(self.julia_controller)
        enabled, active, suppressed, attempted = (list(st.enabled), list(st.active), list(st.suppressed),
                                                  [float(a) for a in st.attempted])
        base_mode = st.baseMode
        return {
            'time': str(st.t) if st.t is not None else None,
            'output_kw': float(st.outputKw),
            'base_kw': float(st.baseKw),
            'base_mode': julia_modes[int(base_mode) - 1].name if base_mode is not None else None,
            'modes': {m.name: {'enabled': bool(enabled[i]), 'active': bool(active[i]),
                               'suppressed': bool(suppressed[i]), 'attempted_kw': attempted[i]}
                      for i, m in enumerate(julia_modes)},
            'bound_lo_kw': float(st.boundLo), 'bound_hi_kw': float(st.boundHi),
            'binding': {'bounds': bool(st.boundBinding), 'reserves': bool(st.reserveBinding),
                        'ramp': bool(st.rampBinding), 'device': bool(st.deviceBinding)},
        }

    # ------------------------------------------------------------------ control
    def apply_energy_limits(self, power: float, duration: timedelta, min_reserve: float = None,
                            max_reserve: float = None):
        """Limit `power` (kW, positive discharging) so the stored energy stays inside the reserve window (percent of
        energy capacity) or the physical window."""
        if self.ess.energy_state is None:
            return 0.0
        hours = duration.total_seconds() / 3600
        if hours <= 0:
            return power
        capacity = self.ess.maximum_energy
        min_energy = min_reserve / 100 * capacity if min_reserve is not None else self.ess.minimum_energy
        max_energy = max_reserve / 100 * capacity if max_reserve is not None else capacity
        stored = self.ess.energy_state
        proposed = stored - power * hours
        if power > 0 and proposed < min_energy:
            return min(power, max((stored - min_energy) / hours, 0.0))
        if power < 0 and proposed > max_energy:
            return max(power, min((stored - max_energy) / hours, 0.0))
        return power

    def control(self, schedule_period: SchedulePeriod, start_time: datetime, sp_progress: VariableIntervalTimeSeries):
        self.last_control_time = start_time
        # The engine-backed modes are combined by one Julia MesaController (IEEE 1815.2 Table 58). The native modes
        # add to its output, reactive modes feed the reactive axis and emergency modes gate the final command.
        power = 0.0
        if self.julia_controller is not None:
            rt = self.julia_modes()[0].runtime
            output = rt.CEE.control(rt.mock_ess(self.ess), self.julia_controller, rt.schedule_period(schedule_period),
                                    rt.use_cases(self.use_cases), rt.datetime(start_time),
                                    rt.progress(start_time, self.resolution, self.ess.power))
            power = float(rt.CEE.raw_vector(output)[0])
        reactive_power_sum = 0.0
        emergency_modes = []
        has_reactive_modes = False
        for mode in self.modes:
            if isinstance(mode, ESControlMode):
                continue
            if isinstance(mode, EmergencyMesaMode):
                emergency_modes.append(mode)
                continue
            mode.wip.append(0.0)
            mode_power = mode.control(schedule_period, start_time, sp_progress)
            mode.wip[-1] = mode_power
            power += mode_power
            if isinstance(mode, ReactiveMesaMode):
                has_reactive_modes = True
                reactive_power_sum += mode.control_reactive(schedule_period, start_time, sp_progress)
        ess_limited_power = min(max(power, self.ess.minimum_power), self.ess.maximum_power)
        energy_limited_power = self.apply_energy_limits(ess_limited_power, self.resolution)
        # Clamp reactive power to the ESS reactive range.
        reactive_power = min(max(reactive_power_sum, self.ess.minimum_reactive_power),
                             self.ess.maximum_reactive_power)
        # Apply emergency ride-through gating as a final-stage override (in priority order).
        for mode in emergency_modes:
            energy_limited_power, reactive_power = mode.gate(energy_limited_power, reactive_power, start_time)
        self.wip.append(energy_limited_power)
        self._last_reactive_command = reactive_power
        # Actuate the reactive axis whenever a reactive or emergency mode is present.
        self._has_reactive_modes = has_reactive_modes or bool(emergency_modes)
        return FixedIntervalTimeSeries(start_time, self.resolution, [energy_limited_power])

    def loop(self):
        if self._stop:
            return
        now = get_aware_utc_now()
        current_schedule_period = next(
            filter(lambda s: s.t_start <= now < s.end_time, self.schedule), SchedulePeriod(0.0, now)
        )
        command = self.control(current_schedule_period, now, VariableIntervalTimeSeries())
        if self.ess.power_command != command[0]:
            _log.debug(f'self.ess.power_command: {self.ess.power_command} is not the same as new command: {command[0]}.'
                       f' Setting!')
            self.ess.power_command = command[0]
        else:
            _log.debug(f'Skipping actuation, command: {command[0]} already matches ess.power_command:'
                       f' {self.ess.power_command}.')
        # Actuate the reactive-power axis when reactive/emergency modes are configured.
        if self._has_reactive_modes and self.ess.reactive_power_command != self._last_reactive_command:
            _log.debug(f'Setting reactive command: {self._last_reactive_command} kVAR.')
            self.ess.reactive_power_command = self._last_reactive_command
        self.publish_status()

    @Core.receiver('onstop')
    def on_stop(self, _):
        _log.debug('In on_stop method.')
        self._stop = True
        super(RTControlAgent, self).on_stop(None)


def main():
    """Main method called by the app."""
    try:
        vip_main(RTControlAgent)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    """Entry point for script"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
