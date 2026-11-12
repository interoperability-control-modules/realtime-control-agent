from rt_control.modes.engine.es_control_mode import ESControlMode


class ChargeDischargeStorage(ESControlMode):
    """Charge/Discharge Storage (IEEE 1815.2 6.4.1; DWGC). Replacing.

    Parameters: ``WSpt`` (kW target), ``GnWPctSpt`` (percent of WMax, negative percent of ChaWMax), ``UseRmpRte``
    (ramp rates vs time constants), the ramp fields. Without a target the mode follows the schedule.
    The storage-wide reserves (DWGC.SocUseMinPct/SocUseMaxPct) are controller settings, see the agent's ``controller``
    configuration.
    """
    LN = 'DWGC'
    JULIA_TYPE = 'ChargeDischargeStorageMode'
    FIELDS = ('WSpt', 'GnWPctSpt', 'UseRmpRte')
    REQ_FIELD = 'ReqW'
    ALIASES = {'active_power_target_kw': 'WSpt', 'active_power_target_percent': 'GnWPctSpt',
               'active_power_target': 'GnWPctSpt', 'use_ramp_rates': 'UseRmpRte'}
