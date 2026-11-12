from datetime import datetime, timezone

from rt_control.use_cases import UseCase


class VariabilityMitigation(UseCase):
    def __init__(self, metered_power_topic: str, metered_power_point: str,
                 rated_power_kw: float, **kwargs):
        super(VariabilityMitigation, self).__init__(**kwargs)
        self.rated_power_kw: float = rated_power_kw
        pubsub_kwargs = {'all_platforms': True} if kwargs.get('subscribe_all_platforms') else {}
        self.controller.vip.pubsub.subscribe('pubsub', metered_power_topic,
                                             self._ingest_state('metered_power', metered_power_point, default=0.0),
                                             **pubsub_kwargs)

    @property
    def forecast_power(self):
        return 0.0  # TODO: Implement this?

    @property
    def metered_power(self):
        return self.states.get('metered_power', 0.0)

    def to_julia(self, cee):
        return cee.EnergyStorageUseCases.VariabilityMitigation(
            cee.FixedIntervalTimeSeries(datetime.now(timezone.utc), self.controller.resolution, [self.metered_power]),
            self.rated_power_kw
        )