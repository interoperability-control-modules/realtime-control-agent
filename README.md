# 🔋 Real-time control Agent

[//]: # (![Eclipse VOLTTRON 11.0.0rc1]&#40;https://img.shields.io/badge/Eclipse%20VOLTTRON-11.0.0rc1-red.svg&#41;)

[//]: # (![Python 3.10]&#40;https://img.shields.io/badge/python-3.10-blue.svg&#41;)

[//]: # (![Python 3.11]&#40;https://img.shields.io/badge/python-3.11-blue.svg&#41;)

[//]: # ([![pypi version]&#40;https://img.shields.io/pypi/v/volttron-interoperability.svg&#41;]&#40;https://pypi.org/project/volttron-interoperability/&#41;)

[//]: # ()
[//]: # (Main branch tests:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; [![Main Branch Passing?]&#40;https://github.com/eclipse-volttron/volttron-interoperability/actions/workflows/run-tests.yml/badge.svg?branch=main&#41;]&#40;https://github.com/eclipse-volttron/volttron-interoperability/actions/workflows/run-tests.yml&#41;)

[//]: # ()
[//]: # (Develop branch tests:&nbsp;&nbsp; [![Develop Branch Passing?]&#40;https://github.com/eclipse-volttron/volttron-interoperability/actions/workflows/run-tests.yml/badge.svg?branch=develop&#41;]&#40;https://github.com/eclipse-volttron/volttron-interoperability/actions/workflows/run-tests.yml&#41;)


## 🔋 Requirements

* python >= 3.10
* volttron >= 10.0 

## 🔋 Summary

The Real-Time (RT) Control Agent provides a framework for actuating one or more control algorithms
on an energy storage system. The RTControl framework involves the use of three abstract class types:
EnergyStorageSystem, ControlMode, and UseCase.

For each class type there are several built-in subclasses, but user defined classes may also be configured and used.
More detailed documentation can be found on the [Interoperability Framework Control Module](https://interoperability-control-modules.github.io/interoperability-framework-control-module.github.io/) site,
including descriptions of the various classes which are available to represent storage systems,
use cases, and control modes.

## 🔋 Configuration

The agent is configured using a JSON file which accepts the following parameters:

| Parameter                 | Description                                                                         |
|---------------------------|-------------------------------------------------------------------------------------|
| ctrl_eval_engine_app_path | The filesystem path to the app directory of the ctrl_eval_engine repository.        |
| resolution                | The smallest time interval considered by the control.                               |
 | ess                       | A configuration dictionary for the storage system. (see below)                      |
| use_cases                 | A list of configuration dictionaries, one for each use case. (see below)            |
 | modes                     | A list of configuration dictionaries, one for each control mode in use. (see below) |
| mode_package              | Optional. The `rt_control.modes` subpackage a mode's `class_name` is looked up in when it has no `module_name`: `engine` selects the CtrlEvalEngine-backed MESA modes, which share class names with the native modes in `active`. Without it the factory searches `active`, `reactive`, `emergency`, `novel`. |
| controller                | Settings of the IEEE 1815.2 controller that combines the modes: `SocUseMinPct`/`SocUseMaxPct` (storage reserves), `maxRampRates`, `OpnLoopTau`/`OplPct`. |
| hub_topic                 | Optional. Messages in the `rtc_controller` hub format (61850 logical nodes, e.g. `{"DWMX": {"LimW": 50, "ModEna": true}}`) on this topic or any sub-topic set the modes' parameters. A sub-topic belongs to one controlling source (a Resource Bridge bus end); only values that differ from what that source last asserted are applied, so a device republishing its state does not undo a newer command from elsewhere. Messages on the base topic are commands and always apply. |
| status_topic              | Optional. The agent publishes its measurements (`DECP.MMXU.TotW`, `DSTO.SocPct`...) here every control interval, and the modes' parameters and read-backs (`DWMX.ReqWLim`...) too unless `modes_topic` is set. |
| modes_topic               | Optional. A separate topic for the modes' parameters and read-backs, so a bridge carrying measurements to a device does not also carry setpoints into it. |

The `ess`, `modes`, and `use_cases` keys are used to configure the options for these respective classes.
`ess` takes a single dictionary, while `modes` and `use_cases` can each accept a list JSON objects (dictionaries).
Each dictionary defines a single class of the appropriate type. Every object in these categories can accept at least
the following two parameters, which tell the agent where to find the class being configured.
Each configuration may also accept additional arguments determined by the specific class.

| Parameter              | Description                                                                                                                                                        |
|------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| class_name             | The name of the object class to be instantiated.                                                                                                                   |
| module_name (optional) | The name of the module in which a custom class can be located. This parameter is optional if the module name is a snake_case version of the camel-cased ClassName. |


#### 🔋 ESS Settings (`ess`)

The ess key takes a single dictionary which defines how the agent interacts with the storage device.
All ess classes can take the parameters listed in the following table.
Specific storage devices may require a concrete subclass of the ESS class, and will also accept additional
parameters, as necessary to configure that device.

| Parameter           | Description                                                                     |
|---------------------|---------------------------------------------------------------------------------|
| ess_topic           | A VOLTTRON topic which will be monitored for publishes from the storage device. |
 | soc_point           | The point name to read state of charge from publishes on the ess_topic.         |
 | power_reading_point | The point name to read power from publishes on the ess_topic.                   |
 | power_command_topic | A VOLTTRON topic which will be used to command power set points.                |
| power_command_point | The point name to write set point commands on the power_command_topic.          |
 | actuator_vip        | The VOLTTRON vip-identity of the agent being used to actuate the ESS.           |
 | actuation_method    | The method name used to command the actuator agent over RPC.                    |
 | actuation_kwargs    | Any keyword arguments to be provided to the actuator agent.                     |
 | rounding_precision  | The number of decimal places to which to round values when commanding power.    |

#### 🔋 Use Case Settings (`use_cases`)

Use cases collect information about the state of the system which will be consumed by the control modes to
make decisions regarding the operation of the storage device. This information is generally obtained from
other agents via the VOLTTRON message bus. A use case may require multiple data points, though all current
use case implementations only require one. Each data-point requires two configuration keys in the
dictionary for that use case: a topic on which to subscribe for data and the point name to identify the data
in the received messages.  For each data point, the user should specify two configurations:
`<identifier_name>_topic` and `<identifier_name>_point`(where "<identifier_name>" should be replaced by the
appropriate names in the table below). For example, the Energy Arbitrage use case uses
`actual_price_topic` and `actual_price_point`.

| Use Case               | Identifier Name   | Description                           |
|------------------------|-------------------|---------------------------------------|
| Energy Arbitrage       | actual_price      | The current price of energy.          |
| Frequency Response     | metered_frequency | Frequency at the reference meter.     |
| Generation Following   | realtime_power    | Power at the reference meter.         |
 | Load Following         | realtime_power    | Power at the reference meter.         |
| Peak Limiting          | realtime_power    | Power at the reference meter.         |
| Regulation             | agc_signal        | The command from the system operator. |
| Variability Mitigation | metered_power     | Power at the reference meter.         |

#### 🔋 Mode Settings (`modes`)

Modes backed by the CtrlEvalEngine implement the IEEE 1815.2 (MESA-ESS) functions and are combined by one Julia
`MesaController`: the highest-priority *replacing* mode (Charge/Discharge Storage, AGC, Coordinated Charge/Discharge)
sets the base power, *additive* modes (Frequency-Watt, Volt-Watt, Dynamic Volt-Watt, Smoothing, Load/Generation
Following) add to it, and *bounding* modes (Active Power Limit, Peak Power Limiting) clamp the result regardless of
priority. Every engine-backed mode accepts the shared parameters `priority` (`ModPrio`), `enabled` (`ModEna`),
`time_window` (`WinTms`), `ramp_time` (`RmpTms`) and `reversion_timeout` (`RvrtTms`, seconds), the ramp parameters
of the table further down, and its own parameters under their IEC 61850 data object names or the readable aliases
listed here. The RPC methods `enable_mode`, `disable_mode`, `set_mode_parameter`, `get_mode_parameters`,
`get_point_map` and `get_status` change and inspect modes at run time; `get_point_map` returns the 61850 point
(`DWMX.LimW`, ...) behind each parameter.

A `controller` section of the configuration carries the controller-wide settings: `SocUseMinPct` and `SocUseMaxPct`
(storage reserves, percent of energy capacity), `maxRampRates` (`RpuRteMax`, `RpdRteMax`, `RpuChaRteMax`,
`RpdChaRteMax`, percent per second), `OpnLoopTau` and `OplPct` (how time constants are read), `randomSeed`.

| Engine-backed mode (class_name)          | 61850 node | Parameters (61850 name — alias)                                                                                                                                                                                                                                                                                                      |
|------------------------------------------|------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ChargeDischargeStorage                   | DWGC       | WSpt — active_power_target_kw; GnWPctSpt — active_power_target_percent; UseRmpRte — use_ramp_rates                                                                                                                                                                                                                                   |
| ActivePowerLimit                         | DWMX/DWMN  | LimWMax — maximum_percent; LimWMin — minimum_percent (negative: consumption cap); LimWMaxKw, LimWMinKw; EcpRef — signal_meter                                                                                                                                                                                                         |
| AGC                                      | DAGC       | WSpt — active_power_target_kw; UseRmpRte; SocUseMinPct — minimum_usable_soc; SocUseMaxPct — maximum_usable_soc                                                                                                                                                                                                                      |
| CoordinatedChargeDischarge               | DTCD       | SocUseTgtPct — target_soc_percent; DateTgt — target_time; WhReq — energy_request_kwh                                                                                                                                                                                                                                                 |
| FrequencyWatt                            | DHFW/DLFW  | HzStrHi/HzStopHi/HzStrLo/HzStopLo — high/low_starting/stopping_frequency; WGraHi/WChaGraHi/WGraLo/WChaGraLo — high/low_discharge/charge_gradient; ActStrDlTmms/ActStopDlTmms — start_delay/stop_delay (ms); SnptEna — use_snapshot_power; HysEna — use_hysteresis; SocUseMinPct/SocUseMaxPct — minimum/maximum_soc; RtnRmpRte; EcpRef |
| FrequencyWattDroop                       | DHFW/DLFW  | HzStrHi/HzStrLo (deadband edges); WGraHi/WGraLo — high/low_gradient; WMinPct/WMaxPct — minimum/maximum_power_percent; plus the shared Frequency-Watt parameters                                                                                                                                                                      |
| FrequencyWattCurve                       | DHFW/DLFW  | HzWCrv — frequency_watt_curve (`[[x, y], ...]` or `{"crvPts": [...]}`); plus the shared Frequency-Watt parameters                                                                                                                                                                                                                      |
| VoltWatt                                 | DVWC       | VWCrv — volt_watt_curve; VWCrvLo — volt_watt_curve_low; VRefOfs — reference_voltage_offset; FilTms — filter_time (s); UseRmpRte; EcpRef                                                                                                                                                                                              |
| DynamicVoltWatt                          | DVWD       | DynVWGra — gradient; DbVWLo/DbVWHi — lower/upper_deadband; VWFilTms — filter_time (s); EcpRef                                                                                                                                                                                                                                         |
| ActivePowerSmoothing                     | DWSM       | WSmthGra — smoothing_gradient; WSmthLoLim/WSmthHiLim — lower/upper_smoothing_limit; FilTms — smoothing_filter_time (s); EcpRef                                                                                                                                                                                                       |
| PeakPowerLimiting, LoadFollowing, GenerationFollowing | DWFL1..3 | FolWThr — activation_threshold (kW); FolWPct — output_ratio (%); SocUseMinPct/SocUseMaxPct — minimum/maximum_soc; EcpRef                                                                                                                                                                                                 |

The Python-only modes below are kept for compatibility; their outputs are added to the engine's result and are not
subject to the combination rules above.

| Control Mode             | Parameter                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Active Power Response    | &#x2022;&nbsp;activation_threshold: float</br>&#x2022;&nbsp;output_ratio: float</br>&#x2022;&nbsp;ramp_params: dict (Python implementation; prefer PeakPowerLimiting / LoadFollowing / GenerationFollowing)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| PID                      | &#x2022;&nbsp;resolution</br>&#x2022;&nbsp;kp</br>&#x2022;&nbsp;ti</br>&#x2022;&nbsp;td                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Rule Based               | &#x2022;&nbsp;bound: float                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |

Engine-backed modes take their ramp parameters as top-level keys (IEEE 1815.2 6.1.5/6.1.6; percent per second of
the power rating, or seconds for time constants):

| Ramping Type  | Parameter (61850 name — alias)                                                                                                                                                                      |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Time Constant | RmpUpTms — ramp_up_time_constant; RmpDnTms — ramp_down_time_constant                                                                                                                                 |
| Ramp Rate     | RpuRte — discharge_ramp_up_rate; RpdRte — discharge_ramp_down_rate; RpuChaRte — charge_ramp_up_rate; RpdChaRte — charge_ramp_down_rate                                                               |

The modes above command **active power** (kW). The agent also supports **reactive power** (kVAR)
modes and **emergency ride-through** modes. Reactive modes contribute a reactive-power command on a
separate axis, which is clamped to the ESS reactive range and actuated when any reactive or emergency
mode is configured. Emergency ride-through modes run last and gate (override) the summed active and
reactive output in priority order.

##### 🔋 Reactive Power Modes

| Control Mode                    | Parameter                                                                                                                                                                         |
|---------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Constant VAR                    | &#x2022;&nbsp;reactive_power_target: float                                                                                                                                       |
| Fixed Power Factor              | &#x2022;&nbsp;power_factor_generating: float</br>&#x2022;&nbsp;power_factor_charging: float = None                                                                               |
| Volt-VAR                        | &#x2022;&nbsp;volt_var_curve: List[Tuple[float, float]]</br>&#x2022;&nbsp;reference_voltage_offset: float = 0.0                                                                  |
| Watt-VAR                        | &#x2022;&nbsp;watt_var_curve: List[Tuple[float, float]]                                                                                                                          |
| Power Factor Correction         | &#x2022;&nbsp;average_pf_target: float</br>&#x2022;&nbsp;lower_pf_limit: float = None</br>&#x2022;&nbsp;upper_pf_limit: float = None                                             |
| Dynamic Reactive Current Support | &#x2022;&nbsp;deadband_min_voltage: float = 0.0</br>&#x2022;&nbsp;deadband_max_voltage: float = 0.0</br>&#x2022;&nbsp;gradient_sag: float = 0.0</br>&#x2022;&nbsp;gradient_swell: float = 0.0</br>&#x2022;&nbsp;block_zone_voltage: float = 0.0 |

##### 🔋 Emergency Ride-Through Modes

| Control Mode           | Parameter                                                                                                                                                                          |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Frequency Ride-Through | &#x2022;&nbsp;high_must_trip: float</br>&#x2022;&nbsp;low_must_trip: float</br>&#x2022;&nbsp;high_momentary_cessation: float = None</br>&#x2022;&nbsp;low_momentary_cessation: float = None |
| Voltage Ride-Through   | &#x2022;&nbsp;high_must_trip: float</br>&#x2022;&nbsp;low_must_trip: float</br>&#x2022;&nbsp;high_momentary_cessation: float = None</br>&#x2022;&nbsp;low_momentary_cessation: float = None |

The modes above command **active power** (kW). The agent also supports **reactive power** (kVAR)
modes and **emergency ride-through** modes. Reactive modes contribute a reactive-power command on a
separate axis, which is clamped to the ESS reactive range and actuated when any reactive or emergency
mode is configured. Emergency ride-through modes run last and gate (override) the summed active and
reactive output in priority order.

##### 🔋 Reactive Power Modes

| Control Mode                    | Parameter                                                                                                                                                                         |
|---------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Constant VAR                    | &#x2022;&nbsp;reactive_power_target: float                                                                                                                                       |
| Fixed Power Factor              | &#x2022;&nbsp;power_factor_generating: float</br>&#x2022;&nbsp;power_factor_charging: float = None                                                                               |
| Volt-VAR                        | &#x2022;&nbsp;volt_var_curve: List[Tuple[float, float]]</br>&#x2022;&nbsp;reference_voltage_offset: float = 0.0                                                                  |
| Watt-VAR                        | &#x2022;&nbsp;watt_var_curve: List[Tuple[float, float]]                                                                                                                          |
| Power Factor Correction         | &#x2022;&nbsp;average_pf_target: float</br>&#x2022;&nbsp;lower_pf_limit: float = None</br>&#x2022;&nbsp;upper_pf_limit: float = None                                             |
| Dynamic Reactive Current Support | &#x2022;&nbsp;deadband_min_voltage: float = 0.0</br>&#x2022;&nbsp;deadband_max_voltage: float = 0.0</br>&#x2022;&nbsp;gradient_sag: float = 0.0</br>&#x2022;&nbsp;gradient_swell: float = 0.0</br>&#x2022;&nbsp;block_zone_voltage: float = 0.0 |

##### 🔋 Emergency Ride-Through Modes

| Control Mode           | Parameter                                                                                                                                                                          |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Frequency Ride-Through | &#x2022;&nbsp;high_must_trip: float</br>&#x2022;&nbsp;low_must_trip: float</br>&#x2022;&nbsp;high_momentary_cessation: float = None</br>&#x2022;&nbsp;low_momentary_cessation: float = None |
| Voltage Ride-Through   | &#x2022;&nbsp;high_must_trip: float</br>&#x2022;&nbsp;low_must_trip: float</br>&#x2022;&nbsp;high_momentary_cessation: float = None</br>&#x2022;&nbsp;low_momentary_cessation: float = None |


---


## 🔋 Example Configuration

This configuration defines control logic to perform active power response, for the purpose of peak limiting 
on a simulated Battery Energy Storage System (ESS).

```json
{
  "ess": {
    "class_name": "FakeESS",
    "power_capacity_kw": 100,
    "energy_capacity_kwh": 125,
    "bess_topic": "devices/PNNL/BESS",
    "soc_point": "SoC",
    "power_reading_point": "",
    "actuator_vip": "",
    "power_command_point": ""
  },
  "modes": [
    {
      "name": "ActivePowerResponseName",
      "class_name": "ActivePowerResponse",
      "activation_threshold": 10.0,
      "output_ratio": 1.0,
      "ramp_params": {}
    }
  ],
  "use_cases": [
    {
      "class_name": "PeakLimiting",
      "realtime_power_topic": "devices/SomeLoad/RealPower"
    }
  ],
  "resolution": 5.0,
  "start_time": null
}
```

## 🔋  Installation

Before installing, VOLTTRON should be installed and running.  Its virtual environment should be active.
Information on how to install of the VOLTTRON platform can be found
[here](https://github.com/eclipse-volttron/volttron-core).

#### 🔋 Install and start the RealTime Control Agent:

```shell
vctl install realtime-control-agent --vip-identity der.rtc --tag rtc --start
```

#### 🔋 Julia and the CtrlEvalEngine

Engine-backed modes need Julia (1.10 or later) and the `ctrl-eval-engine/app` project with its dependencies
instantiated; set `ctrl_eval_engine_app_path` and `julia_path` in the agent configuration and install PyJulia
(`pip install julia`, then `python -c "import julia; julia.install(julia='<julia_path>')"`) in the agent's
environment. Two environment notes:

- Python must be dynamically linked (`--enable-shared`; check `sysconfig.get_config_var('Py_ENABLE_SHARED')`).
  With a statically linked Python PyJulia falls back to `compiled_modules=False`, which recompiles every Julia
  package on each start. With a shared Python and warm caches, starting Julia and loading the engine takes a few
  seconds; a start that takes minutes means packages are being precompiled (first run, changed engine source, or
  a changed artifact override).
- The agent process holds the system OpenSSL before Julia starts, so Julia's bundled `OpenSSL_jll` library can fail
  to load when its version is newer than the system's (`version 'OPENSSL_3.3.0' not found`). Point the JLL's
  artifact at a directory whose `lib/libssl.so` and `lib/libcrypto.so` are symlinks to the system libraries, in
  `~/.julia/artifacts/Overrides.toml` of the user running the agent:

  ```toml
  [458c3c95-2e84-50aa-8efc-19380b2a3a95]
  OpenSSL = "/home/<user>/.julia/openssl-system"
  ```

  ```shell
  mkdir -p ~/.julia/openssl-system/lib
  ln -s /usr/lib64/libssl.so.3 ~/.julia/openssl-system/lib/libssl.so
  ln -s /usr/lib64/libcrypto.so.3 ~/.julia/openssl-system/lib/libcrypto.so
  ```

`test/test_julia_control.py` and `test/test_agent_control.py` exercise the engine and the agent's control path
without a VOLTTRON platform (`CEE_APP_PATH=... JULIA=... python test/test_agent_control.py`).

                                                                                                                                                                |

