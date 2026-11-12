from datetime import datetime, timezone

from rt_control.use_cases import UseCase


class VoltageControl(UseCase):
    def __init__(self, metered_voltage_topic: str, metered_voltage_point: str,
                 reference_voltage: float, **kwargs):
        super(VoltageControl, self).__init__(**kwargs)
        self.reference_voltage: float = reference_voltage
        pubsub_kwargs = {'all_platforms': True} if kwargs.get('subscribe_all_platforms') else {}
        self.controller.vip.pubsub.subscribe('pubsub', metered_voltage_topic,
                                             self._ingest_state('metered_voltage', metered_voltage_point, default=0.0),
                                             **pubsub_kwargs)

    @property
    def forecast_power(self):
        return 0.0  # TODO: Implement this?

    @property
    def metered_voltage(self):
        return self.states.get('metered_voltage', 0.0)

    def to_julia(self, cee):
        return cee.EnergyStorageUseCases.VoltageControl(
            cee.FixedIntervalTimeSeries(datetime.now(timezone.utc), self.controller.resolution, [self.metered_voltage]),
            self.reference_voltage
        )