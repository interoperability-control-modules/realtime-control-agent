"""
Smoke test of the Julia MESA controller through PyJulia, without VOLTTRON.

    CEE_APP_PATH=/path/to/ctrl-eval-engine/app JULIA=/path/to/julia python test/test_julia_control.py
"""
import os
from datetime import datetime, timedelta, timezone

from julia.api import LibJulia

julia_path = os.environ.get('JULIA', 'julia')
app_path = os.environ.get('CEE_APP_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'ctrl-eval-engine', 'app'))
try:
    api = LibJulia.load(julia=julia_path)
    api.init_julia([f'--project={app_path}'])
except Exception:
    from julia.api import Julia
    Julia(compiled_modules=False, runtime=julia_path, project=app_path)

from julia import CtrlEvalEngine, Dates, Main
from julia.CtrlEvalEngine.EnergyStorageSimulators import MockES_Specs, MockES_States, MockSimulator
from julia.CtrlEvalEngine.EnergyStorageScheduling import create_schedule_period
from julia.CtrlEvalEngine import EnergyStorageRTControl as ES

now = Dates.DateTime(2024, 8, 21, 12, 15, 27)
ess = MockSimulator(MockES_Specs(500.0, 1000.0, 1.0), MockES_States(0.5))

modes = [
    ES.ChargeDischargeStorageMode(ES.MesaModeParams(2), GnWPctSpt=53.0,
                                  rampParams=ES.RampParams(10.0, 20.0, 10.0, 20.0)),
    ES.ActivePowerLimitMode(ES.MesaModeParams(1), LimWMax=40.0, LimWMin=-50.0),
]
controller = ES.MesaController(modes, Dates.Second(1))
schedule_period = create_schedule_period(342.0, now, duration=Dates.Second(10))
use_cases = []   # arrives in Julia as Vector{Any}; the MESA control narrows it
progress = CtrlEvalEngine.VariableIntervalTimeSeries([now], [])

outputs = []
t = now
for _ in range(6):
    sequence = CtrlEvalEngine.control(ess, controller, schedule_period, use_cases, t, progress)
    p = CtrlEvalEngine.raw_vector(sequence)[0]
    outputs.append(p)
    CtrlEvalEngine.EnergyStorageSimulators.operate_b(ess, p, Dates.Second(1))
    progress = CtrlEvalEngine.VariableIntervalTimeSeries([now, t + Dates.Second(1)], [p])
    t = t + Dates.Second(1)

# 10 %/s of 500 kW ramps 50 kW per second toward 265 kW; the 40 % limit caps the result at 200 kW.
assert outputs == [50.0, 100.0, 150.0, 200.0, 200.0, 200.0], outputs
status = ES.mesa_status(controller)
assert status.boundBinding and list(status.active) == [True, True], status
print('MESA controller through PyJulia OK:', outputs)
