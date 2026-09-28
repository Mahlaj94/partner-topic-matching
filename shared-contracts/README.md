# shared-contracts

Tiny Python package with shared **types** and **request/response contracts** used by all services in the competence-matrix system.

## Install (editable)
```bash
pip install -e .
```

## Contents
- `shared_contracts.models` — core domain models (Topic, Partner, Chunk, Evidence, Verdict, enums)
- `shared_contracts.contracts` — request/response schemas for service APIs
- `shared_contracts.settings` — central environment/config definitions

## Quick usage
```python
from shared_contracts.models import Topic, Partner, Label, Verdict, Evidence

topic = Topic(
    id="mbse",
    name="MBSE",
    definition="Model-based systems engineering using SysML and related practices.",
    synonyms=["model based systems engineering", "sysml", "system architecture"],
    exclusions=["music", "unrelated 'mbse' acronyms"],
)

partner = Partner(
    id="demo_partner",
    name="Example Robotics",
    domains=["https://example.com/"],
    aliases=["Example Robotics Ltd"],
)

print(topic.model_dump_json(indent=2))
```

Contracts are intentionally **strict** to avoid accidental schema drift across services.
