from pathlib import Path

def test_production_compose_has_worker_and_services():
    text = Path("docker-compose.v1.yml").read_text()
    for name in ["db:", "redis:", "clamav:", "api:", "worker:", "minio:"]:
        assert name in text
    assert "read_only: true" in text
    assert "no-new-privileges:true" in text

def test_production_runbook_exists():
    assert Path("ops/DEPLOYMENT_RUNBOOK.md").exists()
    assert "alembic upgrade head" in Path("ops/DEPLOYMENT_RUNBOOK.md").read_text()

def test_metrics_and_queue_modules_exist():
    assert Path("app/services/queue.py").exists()
    assert Path("app/services/observability.py").exists()
    assert Path("app/api/metrics.py").exists()
