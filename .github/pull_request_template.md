## Summary
<!-- Brief description of changes -->

## Checklist

### General
- [ ] Code follows project style guidelines
- [ ] Self-review completed

### Database/Migrations (if applicable)
- [ ] `alembic heads` shows single head (no multiple heads)
- [ ] `alembic upgrade head` applies successfully on clean DB
- [ ] `alembic check` shows no pending model changes
- [ ] Migration is reversible (`alembic downgrade` works)

### Testing
- [ ] `vedro run` passes locally
- [ ] New functionality has test coverage
