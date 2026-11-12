import logging

from importlib.metadata import distribution, PackageNotFoundError
try:
    distribution('volttron-core')
    from volttron.client.logs import setup_logging
except PackageNotFoundError:
    from volttron.platform.agent.utils import setup_logging

from rt_control.modes import ReactiveMesaMode
from rt_control.use_cases.voltage_control import VoltageControl

setup_logging()
_log = logging.getLogger(__name__)


class DynamicReactiveCurrentSupport(ReactiveMesaMode):
    """MESA Dynamic Reactive Current Support mode (DNP3 DRGS logical node).

    Injects capacitive reactive power during voltage sags and absorbs (inductive)
    reactive power during swells, proportional to how far the metered voltage deviates
    from a reference (nominal) voltage, once the deviation leaves a configured deadband.

    Parameters (percentages, per the DRGS mapping):
      - deadband_min_voltage (DbVMin, <= 0): support applies only when the deviation
        drops below this percent (a sag).
      - deadband_max_voltage (DbVMax, >= 0): support applies only when the deviation
        rises above this percent (a swell).
      - gradient_sag (ArGraSag): percent of rated reactive power applied capacitively per
        percent of negative voltage deviation.
      - gradient_swell (ArGraSwl): percent of rated reactive power applied inductively per
        percent of positive voltage deviation.
      - block_zone_voltage (BlkZnV): below this percent of nominal, no support is applied.

    New native implementation (no Julia fallback). This uses the instantaneous metered
    voltage as the moving-average proxy; it does not implement the DRGS filter time,
    hold-time event latching, or block-zone hysteresis timers.
    """
    def __init__(self, deadband_min_voltage: float = 0.0, deadband_max_voltage: float = 0.0,
                 gradient_sag: float = 0.0, gradient_swell: float = 0.0,
                 block_zone_voltage: float = 0.0, **kwargs):
        super(DynamicReactiveCurrentSupport, self).__init__(**kwargs)
        self.deadband_min_voltage: float = deadband_min_voltage
        self.deadband_max_voltage: float = deadband_max_voltage
        self.gradient_sag: float = gradient_sag
        self.gradient_swell: float = gradient_swell
        self.block_zone_voltage: float = block_zone_voltage

    def control_reactive(self, schedule_period, start_time, sp_progress):
        voltage_control = next((c for c in self.use_cases if isinstance(c, VoltageControl)), None)
        if voltage_control is None:
            _log.error('DynamicReactiveCurrentSupport requires a VoltageControl use case for the voltage input.')
            return 0.0
        reference_voltage = voltage_control.reference_voltage
        if not reference_voltage:
            _log.error('DynamicReactiveCurrentSupport requires a non-zero reference_voltage.')
            return 0.0

        voltage = voltage_control.metered_voltage
        voltage_percent = voltage / reference_voltage * 100
        deviation = (voltage - reference_voltage) / reference_voltage * 100  # percent deviation

        # Below the block-zone voltage, apply no support.
        if voltage_percent < self.block_zone_voltage:
            _log.debug(f'DRCS: voltage {voltage_percent}% below block zone {self.block_zone_voltage}%; no support.')
            return 0.0

        if deviation < self.deadband_min_voltage:
            # Sag: inject capacitive VARs (positive) proportional to depth past the deadband.
            excess = self.deadband_min_voltage - deviation  # positive magnitude
            var_percent = self.gradient_sag * excess
        elif deviation > self.deadband_max_voltage:
            # Swell: absorb inductive VARs (negative) proportional to height past the deadband.
            excess = deviation - self.deadband_max_voltage  # positive magnitude
            var_percent = -self.gradient_swell * excess
        else:
            var_percent = 0.0

        reactive_power = var_percent / 100 * self.ess.maximum_reactive_power
        _log.debug(f'DRCS: V={voltage} ({deviation:.2f}% dev) -> {var_percent:.2f}% -> {reactive_power} kVAR')
        return reactive_power
