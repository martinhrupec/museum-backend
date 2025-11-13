<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 (initial) → 1.0.0
Modified principles: N/A (initial version)
Added sections: 
  - Core Principles (I-VII)
  - Architecture & Technology Stack
  - Development Workflow & Quality Standards
  - Governance
Removed sections: N/A
Templates requiring updates:
  ✅ .specify/templates/plan-template.md (Constitution Check section aligns)
  ✅ .specify/templates/spec-template.md (user stories & requirements align)
  ✅ .specify/templates/tasks-template.md (test categorization aligns)
Follow-up TODOs: None
-->

# Museum Guard Shift Manager Backend Constitution

## Core Principles

### I. Clean Architecture & Separation of Concerns

The codebase MUST maintain clear separation between layers. Business logic MUST NOT reside in views or serializers.

**Required structure:**
- **Views**: Handle HTTP requests/responses, call services, return serialized data
- **Services**: Contain business logic, orchestrate models, implement domain rules
- **Models**: Define data structure and basic validations only
- **Serializers**: Handle data transformation and input/output validation only

**Rationale**: Ensures testability, reusability, and maintainability. Fat models and fat views create tight coupling and make testing difficult.

### II. Test-First Development (NON-NEGOTIABLE)

All new features MUST include tests before implementation approval. The TDD cycle is mandatory: Tests written → User approved → Tests fail → Implementation → Tests pass.

**Test categories MUST include:**
- `tests/unit/` → Individual modules and services (isolated logic)
- `tests/integration/` → Database + ORM behavior (Django models, queries)
- `tests/api/` → Endpoints using DRF test client (request/response cycles)

**Coverage goal**: 100% for core business logic and services. Testing framework: pytest + pytest-django + factory-boy.

**Rationale**: Tests provide documentation, prevent regressions, and ensure code meets requirements before deployment.

### III. Configuration as Environment Variables

All environment-specific configuration MUST follow 12-factor app principles. No hardcoded credentials, URLs, or environment-specific values in source code.

**Required practices:**
- Use environment variables for database connections, API keys, feature flags
- Support for dev/prod/test settings modules
- Default values for development; require explicit values for production
- Document all required environment variables in README.md

**Rationale**: Enables secure, portable deployments across environments without code changes.

### IV. API-First with Standards Compliance

All endpoints MUST be designed using Django REST Framework with OpenAPI documentation generated automatically.

**Required standards:**
- RESTful endpoint design (proper HTTP verbs, status codes, resource naming)
- OpenAPI schema available at `/api/schema/` endpoint
- Use drf-spectacular or drf-yasg for auto-documentation
- Version APIs when breaking changes introduced

**Rationale**: Ensures API discoverability, client generation capabilities, and adherence to industry standards.

### V. Modularity & DRY Principles

Code MUST be modular and reusable. Avoid duplication through shared utilities, base classes, and service extraction.

**Current scope**: All functionality resides in the `api` app until complexity requires splitting. Split ONLY when justified by:
- Clear domain boundaries emerge
- Single app exceeds ~15 models or ~20 endpoints
- Independent deployment needs arise

**Required practices:**
- Extract shared logic to `api/services/` modules
- Use Django signals cleanly for decoupled event handling
- Implement Celery tasks for background processing when needed
- Dependency injection pattern for service instantiation

**Rationale**: Prevents over-engineering while maintaining extensibility. YAGNI principle: don't split until necessary.

### VI. Type Safety & Documentation

All public functions and services MUST include type hints and docstrings.

**Required documentation:**
- Function/method signatures with type hints (PEP 484)
- Docstrings for all public APIs (Google or NumPy style)
- Each app includes README.md with: purpose, key models/serializers/views, example API calls
- Inline comments for complex business logic only

**Rationale**: Improves IDE support, catches errors earlier, and serves as living documentation.

### VII. Simplicity & Standard Django

Prefer Django built-ins over custom implementations. Avoid over-engineering and unnecessary abstractions.

**Guidelines:**
- Use Django ORM, forms, admin, signals as designed
- Introduce custom patterns (repositories, CQRS) ONLY when Django patterns insufficient
- Justify all complexity in documentation
- Challenge every new dependency: does Django already solve this?

**Rationale**: Django is battle-tested and well-documented. Custom abstractions add maintenance burden and learning curve.

## Architecture & Technology Stack

### Technology Requirements

- **Framework**: Django + Django REST Framework
- **Database**: PostgreSQL (required for production)
- **Background Tasks**: Celery + Redis/RabbitMQ (when async processing needed)
- **Testing**: pytest, pytest-django, factory-boy
- **Documentation**: drf-spectacular or drf-yasg
- **Python Version**: 3.10+ (specify exact version in `.python-version`)

### Deployment Standards

- **Migrations**: MUST be atomic, reversible, and tested in staging before production
- **Database**: Zero-downtime migrations required for production deployments
- **Secrets**: MUST use environment variables or secret management service (never committed)
- **Static Files**: Configure Django static file handling per 12-factor app principles

## Development Workflow & Quality Standards

### Code Quality Gates

Before merging any feature, the following MUST pass:

1. **Constitution compliance**: Feature adheres to all core principles
2. **Tests pass**: All test categories run successfully with required coverage
3. **Type checking**: No mypy errors (if type checking enabled)
4. **Linting**: Code passes configured linters (flake8, black, isort)
5. **Documentation**: README updated, docstrings present, API docs generated
6. **Migrations**: Generated, tested, and reversible

### Development Process

1. **Feature specification**: Documented in `.specify/specs/[###-feature-name]/spec.md`
2. **Implementation plan**: Created in `.specify/specs/[###-feature-name]/plan.md`
3. **Test scaffolding**: Write tests first, ensure they fail
4. **Implementation**: Write code to pass tests, maintain clean architecture
5. **Review**: Verify constitution compliance and quality gates
6. **Documentation**: Update app README, ensure API docs current

### Folder Structure Standards

Current structure (all in `api` app until split justified):

```
api/
├── models/          # Django models (data layer)
├── serializers.py   # DRF serializers (data transformation)
├── views.py         # DRF views (HTTP layer)
├── services/        # Business logic (create when needed)
├── urls.py          # URL routing
└── admin.py         # Django admin configuration

tests/
├── unit/            # Isolated logic tests
├── integration/     # Database/ORM tests
└── api/             # Endpoint tests
```

## Governance

This constitution supersedes all other development practices and guidelines. All code contributions, pull requests, and architectural decisions MUST comply with these principles.

### Amendment Process

1. **Proposal**: Document proposed change with rationale and impact analysis
2. **Review**: Team review of alignment with project goals
3. **Approval**: Consensus required for changes to core principles
4. **Migration**: Update affected code, templates, and documentation
5. **Version bump**: Follow semantic versioning (MAJOR: breaking principle changes, MINOR: new principles, PATCH: clarifications)

### Compliance & Enforcement

- All pull requests MUST verify constitution compliance during review
- Complexity that violates principles MUST be justified and documented
- Regular retrospectives to ensure constitution remains practical and relevant
- Constitution violations require explicit approval with mitigation plan

### Related Documentation

- Feature specifications: `.specify/specs/[###-feature-name]/spec.md`
- Implementation plans: `.specify/specs/[###-feature-name]/plan.md`
- Task breakdowns: `.specify/specs/[###-feature-name]/tasks.md`

**Version**: 1.0.0 | **Ratified**: 2025-11-12 | **Last Amended**: 2025-11-12
