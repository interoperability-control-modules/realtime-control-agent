"""
Active Power Response functions (IEEE 1815.2 6.4.6; DWFL1..3) backed by the CtrlEvalEngine. ``FolWThr`` is the power
threshold in kW, ``FolWPct`` the ratio in percent; ramp fields ``RpuRte``/``RpdRte``; own SOC window.
"""
from rt_control.modes.engine.es_control_mode import ESControlMode

_FIELDS = ('FolWThr', 'FolWPct', 'SocUseMinPct', 'SocUseMaxPct', 'EcpRef')
_ALIASES = {'activation_threshold': 'FolWThr', 'output_ratio': 'FolWPct', 'minimum_soc': 'SocUseMinPct',
            'maximum_soc': 'SocUseMaxPct', 'signal_meter': 'EcpRef'}


class PeakPowerLimiting(ESControlMode):
    """Peak Power Limiting (DWFL1): a lower bound on the ESS output so import stays under the threshold. Bounding."""
    LN = 'DWFL1'
    JULIA_TYPE = 'PeakPowerLimitingMode'
    FIELDS = _FIELDS
    ALIASES = _ALIASES
    REQ_FIELD = 'ReqW'


class LoadFollowing(ESControlMode):
    """Load Following (DWFL2): discharge by the ratio of the load above the threshold. Additive."""
    LN = 'DWFL2'
    JULIA_TYPE = 'LoadFollowingMode'
    FIELDS = _FIELDS
    ALIASES = _ALIASES
    REQ_FIELD = 'ReqW'


class GenerationFollowing(ESControlMode):
    """Generation Following (DWFL3): absorb the ratio of the generation above the threshold. Additive."""
    LN = 'DWFL3'
    JULIA_TYPE = 'GenerationFollowingMode'
    FIELDS = _FIELDS
    ALIASES = _ALIASES
    REQ_FIELD = 'ReqW'
