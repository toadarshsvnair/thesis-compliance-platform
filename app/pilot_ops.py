from dataclasses import dataclass
from enum import Enum
from typing import Dict

class GateStatus(str, Enum):
    NOT_STARTED = "not_started"
    PASS = "pass"
    FAIL = "fail"
    WAIVED = "waived"

@dataclass
class PilotGate:
    gate_id: str
    title: str
    owner: str
    status: GateStatus = GateStatus.NOT_STARTED
    evidence_ref: str | None = None
    notes: str | None = None

REQUIRED_GATES = [
    ("G01", "OIDC identity configuration and authorization test", "University IT"),
    ("G02", "Database backup and restore test", "Platform Operations"),
    ("G03", "Object-storage encryption and lifecycle configuration", "Platform Operations"),
    ("G04", "ClamAV availability and fail-closed test", "Security"),
    ("G05", "Worker isolation and restricted egress test", "Security"),
    ("G06", "Tenant-isolation authorization test", "Security"),
    ("G07", "CI security gates passed", "DevSecOps"),
    ("G08", "Approved university rule-set and source evidence", "Research Office"),
    ("G09", "Privacy retention and deletion controls approved", "Privacy/Legal"),
    ("G10", "Incident-response contacts and escalation confirmed", "Security"),
    ("G11", "Pilot user training completed", "Research Office"),
    ("G12", "Non-production end-to-end pilot test completed", "Platform Operations"),
]

def initial_gates() -> Dict[str, PilotGate]:
    return {gid: PilotGate(gid, title, owner) for gid, title, owner in REQUIRED_GATES}

def go_live_allowed(gates: Dict[str, PilotGate]) -> bool:
    return all(g.status in {GateStatus.PASS, GateStatus.WAIVED} for g in gates.values())
