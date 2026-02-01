# Summary

<!-- Brief description of changes -->

## Checklist

### General

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Breaking changes documented (if any)
- [ ] Related issue/ticket referenced (if applicable)

### Database/Migrations (if applicable)

- [ ] `alembic heads` shows single head (no multiple heads)
- [ ] `alembic upgrade head` applies successfully on clean DB
- [ ] `alembic check` shows no pending model changes
- [ ] Migration is reversible (`alembic downgrade -1` works)

### Testing

- [ ] `vedro run` passes locally
- [ ] New functionality has test coverage

## Optional

<!-- Fill in these sections if applicable -->

### Type of Change
<!-- feature / bugfix / refactor / docs / test / chore -->

### Screenshots
<!-- If applicable, add screenshots or recordings -->

### Security Considerations
<!-- Any security implications? -->

### Performance Impact
<!-- Expected performance changes? -->
