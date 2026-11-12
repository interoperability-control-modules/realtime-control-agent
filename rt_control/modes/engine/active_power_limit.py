from rt_control.modes.engine.es_control_mode import ESControlMode


class ActivePowerLimit(ESControlMode):
    """Active Power Limiting (IEEE 1815.2 6.4.2; DWMX maximum, DWMN minimum). Bounding.

    ``LimWMax`` (DWMX.LimW) and ``LimWMin`` (DWMN.LimW) are percent of WMax when positive and of ChaWMax when
    negative; ``LimWMaxKw``/``LimWMinKw`` are the watts alternatives. The interval applies regardless of priority.
    """
    LN = 'DWMX'
    JULIA_TYPE = 'ActivePowerLimitMode'
    FIELDS = ('LimWMax', 'LimWMin', 'LimWMaxKw', 'LimWMinKw', 'EcpRef')
    ALIASES = {'maximum_discharge_percentage': 'LimWMax', 'maximum_percent': 'LimWMax',
               'minimum_percent': 'LimWMin', 'maximum_kw': 'LimWMaxKw', 'minimum_kw': 'LimWMinKw',
               'signal_meter': 'EcpRef'}
    HAS_RAMP = False
    LN_FOR_FIELD = {'LimWMin': 'DWMN'}

    def set_parameter(self, name, value, rebuild=True):
        # The old wrapper took the charging limit as a positive percentage; a consumption cap is a negative minimum.
        if name == 'maximum_charge_percentage':
            name, value = 'LimWMin', -abs(float(value))
        super(ActivePowerLimit, self).set_parameter(name, value, rebuild)

    def point_map(self):
        points = super(ActivePowerLimit, self).point_map()
        points['DWMX.LimW'] = points.pop('DWMX.LimWMax')
        points['DWMN.LimW'] = points.pop('DWMN.LimWMin')
        return points
