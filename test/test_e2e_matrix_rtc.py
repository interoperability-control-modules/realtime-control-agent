"""
The RTC agent as the fifth party of the interoperability e2e matrix (MESA plan Phase 7, in-process half).

Runs the interoperability service's matrix harness with ``E2E_RTC=1`` in the Resource Bridge bus mode: the four
protocols' enabled 50 % active power limit reaches the agent's Active Power Limit mode through the `rtc_controller`
format, and the agent's status (its power) reaches each protocol's device and the OpenFMB broker. Needs an environment
with the interoperability service, the driver stack, PyJulia and ``rt_control`` installed, Julia, and the engine project.

    CEE_APP_PATH=... JULIA=... pytest -q test/test_e2e_matrix_rtc.py
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HARNESS = ROOT / 'interoperability_service' / 'tests' / 'e2e_matrix' / 'harness.py'
EXPECTED_PATHS = 24 + 8          # the 24 device/OpenFMB paths plus 4 controls into and 4 telemetry out of the RTC agent


@pytest.mark.skipif(not HARNESS.exists(), reason='interoperability service checkout not found')
def test_matrix_with_rtc_agent(tmp_path):
    env = dict(os.environ, E2E_OPENFMB='bus', E2E_RTC='1', E2E_LOG=str(tmp_path / 'e2e_matrix_rtc.log'))
    env.setdefault('CEE_APP_PATH', str(ROOT / 'ctrl-eval-engine' / 'app'))
    proc = subprocess.run([sys.executable, str(HARNESS), str(tmp_path)], env=env, capture_output=True, text=True,
                          timeout=1800)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out[-6000:]
    assert f'{EXPECTED_PATHS}/{EXPECTED_PATHS} passed' in out, out[-6000:]
    assert out.count('-> RTC ') == 4 and out.count('RTC -> ') == 4, out[-6000:]
