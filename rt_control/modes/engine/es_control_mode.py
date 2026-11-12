"""
MESA modes implemented in the CtrlEvalEngine (Julia), driven through PyJulia.

An `ESControlMode` subclass names the Julia mode type it wraps and the IEC 61850 data objects that type accepts as
parameters. Parameters may be given under their 61850 names (``GnWPctSpt``) or under human-readable aliases
(``active_power_target_percent``); both map onto the same Julia field, so an RPC call and a hub message set the same
thing. The agent builds one Julia ``MesaController`` from every ESControlMode it carries and lets the engine combine
them per IEEE 1815.2 (see ``RTControlAgent.control``); a mode on its own can still be evaluated with ``control``.
"""
import abc
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
    from volttron.utils import parse_timestamp_string
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging, parse_timestamp_string

from rt_control.modes import ControlMode
from rt_control.util import SchedulePeriod

setup_logging()
_log = logging.getLogger(__name__)

SHARED_FIELDS = ('ModEna', 'WinTms', 'RmpTms', 'RvrtTms')
SHARED_ALIASES = {'enabled': 'ModEna', 'time_window': 'WinTms', 'ramp_time': 'RmpTms',
                  'reversion_timeout': 'RvrtTms'}
RAMP_FIELDS = ('RpuRte', 'RpdRte', 'RpuChaRte', 'RpdChaRte', 'RmpUpTms', 'RmpDnTms')
RAMP_ALIASES = {'discharge_ramp_up_rate': 'RpuRte', 'discharge_ramp_down_rate': 'RpdRte',
                'charge_ramp_up_rate': 'RpuChaRte', 'charge_ramp_down_rate': 'RpdChaRte',
                'ramp_up_time_constant': 'RmpUpTms', 'ramp_down_time_constant': 'RmpDnTms'}


def _seconds(value) -> float:
    return value.total_seconds() if isinstance(value, timedelta) else float(value)


def coerce_scalar(value):
    """Values arriving as strings (vctl rpc call, text hub messages) become bool or number when they read as one."""
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ('true', 'false'):
            return low == 'true'
        try:
            return int(low) if low.lstrip('-').isdigit() else float(low)
        except ValueError:
            return value
    return value


class JuliaRuntime:
    """One Julia process per agent, holding the CtrlEvalEngine module and conversion helpers."""
    _instance: Optional['JuliaRuntime'] = None

    def __init__(self, app_path: str, julia_path: str = 'julia'):
        self.app_path = app_path
        self.julia_path = julia_path
        from julia.api import Julia
        try:
            jl = Julia(runtime=julia_path)
        except Exception as e:  # statically linked python: fall back to the slower, compatible start-up
            _log.warning(f'Julia start-up failed ({e}); retrying with compiled_modules=False.')
            jl = Julia(compiled_modules=False, runtime=julia_path)
        jl.eval(f'import Pkg; Pkg.activate(raw"{app_path}"; io=devnull)')
        # Import explicitly so a load failure surfaces with Julia's message instead of PyJulia's "not found".
        jl.eval('import CtrlEvalEngine')
        from julia import CtrlEvalEngine, Dates, Main
        self.CEE = CtrlEvalEngine
        self.ES = CtrlEvalEngine.EnergyStorageRTControl
        self.Dates = Dates
        self.Main = Main

    @classmethod
    def get(cls, app_path: str, julia_path: str = 'julia') -> 'JuliaRuntime':
        if cls._instance is None:
            cls._instance = cls(app_path, julia_path)
        return cls._instance

    # ---- conversions ----
    def seconds(self, value):
        return self.Dates.Second(int(round(_seconds(value))))

    def millis(self, value):
        return self.Dates.Millisecond(int(round(_seconds(value) * 1000)))

    def datetime(self, value):
        if isinstance(value, str):
            value = parse_timestamp_string(value)
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return self.Dates.DateTime(value.year, value.month, value.day, value.hour, value.minute, value.second,
                                   value.microsecond // 1000)

    def symbol(self, name):
        return self.Main.Symbol(str(name))

    def curve(self, points):
        if isinstance(points, dict):
            points = [(pt['xVal'], pt['yVal']) for pt in points['crvPts']]
        return self.ES.VertexCurve([self.ES.Vertex(float(x), float(y)) for x, y in points])

    def schedule_period(self, sp: SchedulePeriod):
        kwargs = {'duration': self.millis(sp.duration)}
        if sp.reg_cap_kw:
            kwargs['regCapKw'] = float(sp.reg_cap_kw)
        return self.CEE.EnergyStorageScheduling.create_schedule_period(float(sp.p), self.datetime(sp.t_start), **kwargs)

    def mock_ess(self, ess):
        """A Julia MockSimulator mirroring the real storage's ratings and state of charge."""
        sims = self.CEE.EnergyStorageSimulators
        return sims.MockSimulator(sims.MockES_Specs(*ess.specs.dump()), sims.MockES_States(ess.soc / 100))

    def progress(self, t: datetime, resolution: timedelta, actual_power_kw: float):
        """A one-interval progress series carrying the ESS's actual power, which the engine ramps from."""
        return self.CEE.VariableIntervalTimeSeries([self.datetime(t - resolution), self.datetime(t)],
                                                   [float(actual_power_kw)])

    def use_cases(self, use_cases: Iterable):
        """The use cases as Julia objects; the MESA `control` narrows the Vector{Any} PyJulia produces."""
        return [u.to_julia(self.CEE) for u in use_cases]


class ESControlMode(ControlMode):
    """Base class for a MESA mode backed by the CtrlEvalEngine.

    Subclasses set ``LN`` (61850 logical node class), ``JULIA_TYPE`` (constructor in
    ``CtrlEvalEngine.EnergyStorageRTControl``), ``FIELDS`` (accepted 61850 parameter names), ``ALIASES``
    (readable name -> 61850 name) and the conversion sets below.
    """
    LN: str = ''
    JULIA_TYPE: str = ''
    FIELDS: tuple = ()
    ALIASES: Dict[str, str] = {}
    HAS_RAMP: bool = True
    CURVE_FIELDS: tuple = ()
    SECONDS_FIELDS: tuple = ()
    MILLIS_FIELDS: tuple = ()
    DATETIME_FIELDS: tuple = ()
    SYMBOL_FIELDS: tuple = ('EcpRef',)
    LN_FOR_FIELD: Dict[str, str] = {}   # overrides LN for fields that belong to a different logical node
    REQ_FIELD: Optional[str] = None     # the 61850 read-back of the attempted output (ReqW, ReqWLim, ReqWSet), if any

    def __init__(self, ctrl_eval_engine_app_path: str, julia_path: str = 'julia', **kwargs):
        base = {k: kwargs.pop(k) for k in ('controller', 'ess', 'use_cases', 'priority') if k in kwargs}
        kwargs.pop('name', None)
        super(ESControlMode, self).__init__(**base)
        self.runtime = JuliaRuntime.get(ctrl_eval_engine_app_path, julia_path)
        self.shared: Dict[str, Any] = {'ModEna': True, 'WinTms': 0, 'RmpTms': 0, 'RvrtTms': 0}
        self.ramp: Dict[str, Any] = {}
        self.params: Dict[str, Any] = {}
        for k, v in kwargs.items():
            self.set_parameter(k, v, rebuild=False)
        self.julia_mode = self.build()

    # ---- parameters ----
    def canonical(self, name: str) -> str:
        return self.ALIASES.get(name) or SHARED_ALIASES.get(name) or RAMP_ALIASES.get(name) or name

    def set_parameter(self, name: str, value, rebuild: bool = True):
        key = self.canonical(name)
        value = coerce_scalar(value)
        if key in ('ModPrio', 'priority'):
            self.priority = int(value)
        elif key in SHARED_FIELDS:
            self.shared[key] = value
        elif key in RAMP_FIELDS:
            self.ramp[key] = value
        elif key in self.FIELDS:
            self.params[key] = value
        else:
            raise KeyError(f'{type(self).__name__} has no parameter "{name}"')
        if rebuild:
            self.julia_mode = self.build()
            if hasattr(self.controller, 'on_mode_changed'):
                self.controller.on_mode_changed(self)

    def get_parameter(self, name: str):
        key = self.canonical(name)
        for store in (self.shared, self.ramp, self.params):
            if key in store:
                return store[key]
        raise KeyError(f'{type(self).__name__} has no parameter "{name}"')

    def parameters(self) -> Dict[str, Any]:
        out = {'ModPrio': self.priority}
        out.update(self.shared)
        out.update(self.ramp)
        out.update(self.params)
        return out

    def point_map(self) -> Dict[str, str]:
        """61850 point name -> parameter name, for the hub format and the 1815.2 outstation."""
        points = {f'{self.LN}.{f}': f for f in ('ModEna', 'ModPrio', 'WinTms', 'RmpTms', 'RvrtTms')}
        for f in self.FIELDS + (RAMP_FIELDS if self.HAS_RAMP else ()):
            ln = self.LN_FOR_FIELD.get(f, self.LN)
            do = f[:-2] if f.endswith(('Hi', 'Lo')) and f in self.LN_FOR_FIELD else f
            points[f'{ln}.{do}'] = f
        return points

    # ---- Julia construction ----
    def mode_params(self):
        rt = self.runtime
        return rt.ES.MesaModeParams(int(self.priority), ModEna=bool(self.shared['ModEna']),
                                    WinTms=rt.seconds(self.shared['WinTms']), RmpTms=rt.seconds(self.shared['RmpTms']),
                                    RvrtTms=rt.seconds(self.shared['RvrtTms']))

    def ramp_params(self):
        rt = self.runtime
        kwargs = {k: (rt.seconds(v) if k in ('RmpUpTms', 'RmpDnTms') else float(v)) for k, v in self.ramp.items()}
        return rt.ES.RampParams(**kwargs)

    def convert(self, key: str, value):
        rt = self.runtime
        if key in self.CURVE_FIELDS:
            return rt.curve(value)
        if key in self.SECONDS_FIELDS:
            return rt.seconds(value)
        if key in self.MILLIS_FIELDS:
            return rt.millis(value)
        if key in self.DATETIME_FIELDS:
            return rt.datetime(value)
        if key in self.SYMBOL_FIELDS:
            return rt.symbol(value)
        return value

    def build(self):
        julia_type = getattr(self.runtime.ES, self.JULIA_TYPE)
        kwargs = {k: self.convert(k, v) for k, v in self.params.items()}
        if self.HAS_RAMP:
            kwargs['rampParams'] = self.ramp_params()
        return julia_type(self.mode_params(), **kwargs)

    # ---- stand-alone evaluation (one-mode controller) ----
    def control(self, schedule_period, start_time, sp_progress) -> float:
        rt = self.runtime
        resolution = self.controller.resolution
        controller = rt.ES.MesaController([self.julia_mode], rt.millis(resolution))
        output = rt.CEE.control(rt.mock_ess(self.ess), controller, rt.schedule_period(schedule_period),
                                rt.use_cases(self.use_cases), rt.datetime(start_time),
                                rt.progress(start_time, resolution, self.ess.power))
        return rt.CEE.raw_vector(output)[0]
