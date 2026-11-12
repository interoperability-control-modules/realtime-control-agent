from rt_control.modes.engine.es_control_mode import ESControlMode


class ActivePowerSmoothing(ESControlMode):
    """Active Power Smoothing (IEEE 1815.2 6.4.8; DWSM). Additive; mutually exclusive with AGC.

    ``WSmthGra`` kW per kW of delta (positive follows load, negative follows generation), ``WSmthLoLim``/``WSmthHiLim``
    the deadband in kW, ``FilTms`` the moving-average window in seconds.
    """
    LN = 'DWSM'
    JULIA_TYPE = 'ActivePowerSmoothingMode'
    FIELDS = ('WSmthGra', 'WSmthLoLim', 'WSmthHiLim', 'FilTms', 'EcpRef')
    ALIASES = {'smoothing_gradient': 'WSmthGra', 'lower_smoothing_limit': 'WSmthLoLim',
               'upper_smoothing_limit': 'WSmthHiLim', 'smoothing_filter_time': 'FilTms', 'signal_meter': 'EcpRef'}
    SECONDS_FIELDS = ('FilTms',)
    REQ_FIELD = 'ReqWSet'
