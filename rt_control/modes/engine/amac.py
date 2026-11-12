from rt_control.modes.engine.es_control_mode import ESControlMode


class AMAC(ESControlMode):
    """Placeholder for the engine's AMAController.

    AMAC is an `RTController` in the engine, an alternative to the MESA controller rather than a mode inside it,
    and needs a PV generation profile plus an external websocket service. Wrapping it as a MESA mode is not
    meaningful; see RTC_AGENT_AND_CTRLEVALENGINE.md section 1.4 for the planned strategy abstraction.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError('AMAC is a whole controller, not a MESA mode; see the strategy design.')
