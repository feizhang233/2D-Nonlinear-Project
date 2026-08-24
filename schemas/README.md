# Schemas

`model-input-1.0.0.schema.json` is the checked-in P1 `ModelInput` JSON Schema. Regenerate it with:

```bash
python scripts/generate_schema.py
```

`openapi-1.0.0.json` is the checked-in P10 FastAPI/OpenAPI contract. Regenerate it with:

```bash
python scripts/generate_openapi.py
```

`model-input-1.0.0.schema.json` is the checked-in Draft 2020-12 schema for `ModelInput`.

Regenerate it after an intentional contract change with:

```bash
python scripts/generate_schema.py
```

JSON Schema validates document structure. Duplicate IDs, cross-entity references, load targets,
and family-specific DOFs are semantic checks performed by `nonlinear_core.validate_model_input`.
