from rt_control.modes.engine.es_control_mode import ESControlMode


class VoltWatt(ESControlMode):
    """Volt-Watt (IEEE 1815.2 6.4.4; DVWC). Additive, composed as a boundary.

    ``VWCrv`` is the high-voltage branch (x percent of VRef, y percent of WMax), ``VWCrvLo`` the optional
    low-voltage branch, ``VRefOfs`` the reference offset in percent, ``FilTms`` the voltage filter in seconds,
    ``UseRmpRte`` whether the ramp rates apply in addition to the time constants.
    """
    LN = 'DVWC'
    JULIA_TYPE = 'VoltWattMode'
    FIELDS = ('VWCrv', 'VWCrvLo', 'VRefOfs', 'FilTms', 'UseRmpRte', 'EcpRef')
    ALIASES = {'volt_watt_curve': 'VWCrv', 'volt_watt_curve_low': 'VWCrvLo',
               'reference_voltage_offset': 'VRefOfs', 'filter_time': 'FilTms', 'use_ramp_rates': 'UseRmpRte',
               'signal_meter': 'EcpRef'}
    CURVE_FIELDS = ('VWCrv', 'VWCrvLo')
    SECONDS_FIELDS = ('FilTms',)
    REQ_FIELD = 'ReqWLim'


class DynamicVoltWatt(ESControlMode):
    """Dynamic Volt-Watt (IEEE 1815.2 6.4.10; DVWD). Additive.

    ``DynVWGra`` percent of WMax per percent voltage deviation from the moving average over ``VWFilTms`` seconds;
    ``DbVWLo``/``DbVWHi`` the deadband in percent.
    """
    LN = 'DVWD'
    JULIA_TYPE = 'DynamicVoltWattMode'
    FIELDS = ('DynVWGra', 'DbVWLo', 'DbVWHi', 'VWFilTms', 'EcpRef')
    ALIASES = {'gradient': 'DynVWGra', 'lower_deadband': 'DbVWLo', 'upper_deadband': 'DbVWHi',
               'filter_time': 'VWFilTms', 'signal_meter': 'EcpRef'}
    HAS_RAMP = False
    SECONDS_FIELDS = ('VWFilTms',)
    REQ_FIELD = 'ReqWSet'
