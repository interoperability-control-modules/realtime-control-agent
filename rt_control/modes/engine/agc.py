from rt_control.modes.engine.es_control_mode import ESControlMode


class AGC(ESControlMode):
    """Automatic Generation Control (IEEE 1815.2 6.4.7; DAGC). Replacing; mutually exclusive with every active power
    function except Charge/Discharge and Active Power Limit.

    ``WSpt`` is the kW target the controlling station updates; without it a Regulation use case supplies the
    per-unit signal. ``SocUseMinPct``/``SocUseMaxPct`` is the function's own usable SOC window.
    """
    LN = 'DAGC'
    JULIA_TYPE = 'AGCMode'
    FIELDS = ('WSpt', 'UseRmpRte', 'SocUseMinPct', 'SocUseMaxPct')
    ALIASES = {'active_power_target_kw': 'WSpt', 'use_ramp_rates': 'UseRmpRte',
               'minimum_usable_soc': 'SocUseMinPct', 'maximum_usable_soc': 'SocUseMaxPct'}
