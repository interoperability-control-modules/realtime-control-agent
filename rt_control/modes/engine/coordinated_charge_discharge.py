from rt_control.modes.engine.es_control_mode import ESControlMode


class CoordinatedChargeDischarge(ESControlMode):
    """Coordinated Charge/Discharge Management (IEEE 1815.2 6.4.5; DTCD). Replacing.

    Reach ``SocUseTgtPct`` percent of usable capacity by ``DateTgt`` (ISO timestamp); ``WhReq`` optionally caps the
    energy moved.
    """
    LN = 'DTCD'
    JULIA_TYPE = 'CoordinatedChargeDischargeMode'
    FIELDS = ('SocUseTgtPct', 'DateTgt', 'WhReq')
    ALIASES = {'target_soc_percent': 'SocUseTgtPct', 'target_time': 'DateTgt', 'energy_request_kwh': 'WhReq'}
    HAS_RAMP = False
    DATETIME_FIELDS = ('DateTgt',)
