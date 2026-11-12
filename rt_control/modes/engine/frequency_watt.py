from rt_control.modes.engine.es_control_mode import ESControlMode

# Fields suffixed Hi belong to DHFW (high frequency), Lo to DLFW (low frequency).
_FW_SIDES = {'HzStrHi': 'DHFW', 'HzStopHi': 'DHFW', 'WGraHi': 'DHFW', 'WChaGraHi': 'DHFW',
             'HzStrLo': 'DLFW', 'HzStopLo': 'DLFW', 'WGraLo': 'DLFW', 'WChaGraLo': 'DLFW'}
_FW_COMMON_FIELDS = ('HzStrHi', 'HzStopHi', 'HzStrLo', 'HzStopLo', 'ActStrDlTmms', 'ActStopDlTmms', 'SnptEna',
                     'HysEna', 'SocUseMinPct', 'SocUseMaxPct', 'RtnRmpRte', 'EcpRef')
_FW_COMMON_ALIASES = {'high_starting_frequency': 'HzStrHi', 'high_stopping_frequency': 'HzStopHi',
                      'low_starting_frequency': 'HzStrLo', 'low_stopping_frequency': 'HzStopLo',
                      'start_delay': 'ActStrDlTmms', 'stop_delay': 'ActStopDlTmms',
                      'use_snapshot_power': 'SnptEna', 'use_hysteresis': 'HysEna',
                      'minimum_soc': 'SocUseMinPct', 'maximum_soc': 'SocUseMaxPct',
                      'return_ramp_rate': 'RtnRmpRte', 'signal_meter': 'EcpRef'}


class FrequencyWatt(ESControlMode):
    """Frequency-Watt sensitivity (IEEE 1815.2 6.4.3.3; DHFW1/DLFW1). Additive.

    Gradients ``WGraHi``/``WGraLo`` are percent of WMax per percent frequency deviation on the discharging side,
    ``WChaGraHi``/``WChaGraLo`` percent of ChaWMax on the charging side. Delays are milliseconds (or timedelta).
    """
    LN = 'DHFW'
    JULIA_TYPE = 'FrequencyWattMode'
    FIELDS = _FW_COMMON_FIELDS + ('WGraHi', 'WChaGraHi', 'WGraLo', 'WChaGraLo')
    ALIASES = dict(_FW_COMMON_ALIASES, high_discharge_gradient='WGraHi', high_charge_gradient='WChaGraHi',
                   low_discharge_gradient='WGraLo', low_charge_gradient='WChaGraLo')
    MILLIS_FIELDS = ('ActStrDlTmms', 'ActStopDlTmms')
    LN_FOR_FIELD = _FW_SIDES
    REQ_FIELD = 'ReqWLim'


class FrequencyWattDroop(ESControlMode):
    """Frequency-Watt droop (IEEE 1815.2 6.4.3.1; DHFW3/DLFW3; IEEE 1547 primary frequency response). Additive.

    ``HzStrHi``/``HzStrLo`` are the deadband edges, ``WGraHi``/``WGraLo`` percent of WMax per percent frequency
    beyond the edge from the pre-disturbance power, ``WMinPct``/``WMaxPct`` the bounds in percent of WMax. The
    open-loop response time goes in ``RmpUpTms``/``RmpDnTms``.
    """
    LN = 'DHFW'
    JULIA_TYPE = 'FrequencyWattDroopMode'
    FIELDS = _FW_COMMON_FIELDS + ('WGraHi', 'WGraLo', 'WMinPct', 'WMaxPct')
    ALIASES = dict(_FW_COMMON_ALIASES, high_gradient='WGraHi', low_gradient='WGraLo',
                   minimum_power_percent='WMinPct', maximum_power_percent='WMaxPct')
    MILLIS_FIELDS = ('ActStrDlTmms', 'ActStopDlTmms')
    LN_FOR_FIELD = _FW_SIDES
    REQ_FIELD = 'ReqWLim'


class FrequencyWattCurve(ESControlMode):
    """Frequency-Watt curve (IEEE 1815.2 6.4.9; DHFW2/DLFW2). Additive.

    ``HzWCrv`` maps percent frequency deviation (x) to percent of WMax (y), as ``[[x, y], ...]`` or the hub's
    ``{"crvPts": [{"xVal", "yVal"}]}``.
    """
    LN = 'DHFW'
    JULIA_TYPE = 'FrequencyWattCurveMode'
    FIELDS = _FW_COMMON_FIELDS + ('HzWCrv',)
    ALIASES = dict(_FW_COMMON_ALIASES, frequency_watt_curve='HzWCrv')
    CURVE_FIELDS = ('HzWCrv',)
    MILLIS_FIELDS = ('ActStrDlTmms', 'ActStopDlTmms')
    LN_FOR_FIELD = _FW_SIDES
    REQ_FIELD = 'ReqWLim'
