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
More detailed documentation can be found on the [Interoperability Framework Control Module](https://interoperability-framework-control-module.github.io/) site,
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

| Control Mode             | Parameter                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Active Power Limit       | &#x2022;&nbsp;maximum_charge_percentage: float</br>&#x2022;&nbsp;maximum_discharge_percentage: float                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Active Power Response    | &#x2022;&nbsp;activation_threshold: float</br>&#x2022;&nbsp;output_ratio: float</br>&#x2022;&nbsp;ramp_params: dict                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Active Power Smoothing   | &#x2022;&nbsp;smoothing_gradient: float</br>&#x2022;&nbsp;lower_smoothing_limit: float</br>&#x2022;&nbsp;upper_smoothing_limit: float</br>&#x2022;&nbsp;smoothing_filter_time: Union[float, timedelta]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| AGC                      | &#x2022;&nbsp;minimum_usable_soc: float</br>&#x2022;&nbsp;maximum_usable_soc: float                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Charge/Discharge Storage | &#x2022;&nbsp;minimum_reserve_percent: float = 10.0</br>&#x2022;&nbsp;maximum_reserve_percent: float = 90.0</br>&#x2022;&nbsp;active_power_target: Union[float, None] = None                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Frequency-Watt           | &#x2022;&nbsp;use_curves: bool</br>&#x2022;&nbsp;frequency_watt_curve: List[Tuple[float, float]]</br>&#x2022;&nbsp;low_hysteresis_curve: List[Tuple[float, float]]</br>&#x2022;&nbsp;high_hysteresis_curve: List[Tuple[float, float]]</br>&#x2022;&nbsp;start_delay: Union[timedelta, float]</br>&#x2022;&nbsp;stop_delay: Union[timedelta, float]</br>&#x2022;&nbsp;minimum_soc: float</br>&#x2022;&nbsp;maximum_soc: float</br>&#x2022;&nbsp;use_hysteresis: bool</br>&#x2022;&nbsp;use_snapshot_power: bool</br>&#x2022;&nbsp;high_starting_frequency: float</br>&#x2022;&nbsp;low_starting_frequency: float</br>&#x2022;&nbsp;high_stopping_frequency: float</br>&#x2022;&nbsp;low_stopping_frequency: float</br>&#x2022;&nbsp;high_discharge_gradient: float</br>&#x2022;&nbsp;low_discharge_gradient: float</br>&#x2022;&nbsp;high_charge_gradient: float</br>&#x2022;&nbsp;low_charge_gradient: float</br>&#x2022;&nbsp;high_return_gradient: float</br>&#x2022;&nbsp;low_return_gradient: float |
| PID                      | &#x2022;&nbsp;resolution</br>&#x2022;&nbsp;kp</br>&#x2022;&nbsp;ti</br>&#x2022;&nbsp;td                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Rule Based               | &#x2022;&nbsp;bound: float                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |

Some modes make use of a ramp_params dictionary to specify how the control will handle transitions between states.
This can be specified using either time constants or ramp rates. 
Where specified, this dictionary may contain the following keys:

| Ramping Type  | Parameter                                                                                                                                                                                                             |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Time Constant | &#x2022;&nbsp;ramp_up_time_constant: float = None</br>&#x2022;&nbsp;ramp_down_time_constant: float = None                                                                                                             |
| Ramp Rate     | &#x2022;&nbsp;discharge_ramp_up_rate: float = 1000</br>&#x2022;&nbsp;discharge_ramp_down_rate: float = 1000</br>&#x2022;&nbsp;charge_ramp_up_rate: float = 1000</br>&#x2022;&nbsp;charge_ramp_down_rate: float = 1000 |

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

                                                                                                                                                                |

