from app.pilot_ops import GateStatus, initial_gates, go_live_allowed

def test_pilot_starts_blocked():
    gates = initial_gates()
    assert len(gates) == 12
    assert not go_live_allowed(gates)

def test_all_pass_allows_go_live():
    gates = initial_gates()
    for gate in gates.values():
        gate.status = GateStatus.PASS
    assert go_live_allowed(gates)

def test_failure_blocks_go_live():
    gates = initial_gates()
    for gate in gates.values():
        gate.status = GateStatus.PASS
    gates["G04"].status = GateStatus.FAIL
    assert not go_live_allowed(gates)

def test_waiver_is_explicit():
    gates = initial_gates()
    for gate in gates.values():
        gate.status = GateStatus.PASS
    gates["G11"].status = GateStatus.WAIVED
    assert go_live_allowed(gates)
