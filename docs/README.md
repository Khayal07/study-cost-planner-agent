# 📚 Documentation

Full documentation for the **Study Abroad Planning Platform**. Start with the
[project README](../README.md) for the overview, then dive in here.

| Doc | Read this if you want to… |
|-----|---------------------------|
| [Architecture](ARCHITECTURE.md) | Understand the multi-agent pipeline, the orchestrator, and how a request flows end to end. |
| [Features](FEATURES.md) | See every user-facing feature explained, with the code paths behind it. |
| [API reference](API.md) | Call the backend — every endpoint, auth, and payload. |
| [Data model](DATA_MODEL.md) | Understand the database schema and the citation contract. |
| [AI data pipeline](DATA_PIPELINE.md) | Add a new field of study with AI-assisted, human-reviewed data collection. |
| [Configuration](CONFIGURATION.md) | Know what every environment variable does. |
| [Security](SECURITY.md) | Understand the threat model, hardening, and the production checklist. |
| [Development](DEVELOPMENT.md) | Run, test, and extend the project locally. |

## The one idea to remember

> **LLM for language, Python for math.**

Every cost, currency conversion, budget gap and eligibility verdict is computed by
**deterministic Python**. The LLM is used only for intent extraction, narration,
verification summaries, and the optional writing/vision/voice features. That's why
every number in the app can be traced back to a cited source.
