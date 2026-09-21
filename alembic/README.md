# Database migrations

Production deployments should run:

```bash
alembic upgrade head
```

After schema changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Review generated SQL before applying it. `Base.metadata.create_all()` remains in the application only for local development convenience; production should use Alembic as the schema authority.
