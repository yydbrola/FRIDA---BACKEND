# Claude Agents

This directory contains specialized agent prompts for the Frida Orchestrator project.

## Available Agents

### Doc Keeper (`doc-keeper.md`)

**Purpose:** Documentation management and context optimization.

**Responsibilities:**
- Keep CLAUDE.md lean (≤600 lines)
- Maintain CHANGELOG.md with version history
- Organize test documentation in TESTS.md
- Prevent context pollution

**How to Invoke:**

```
@doc-keeper.md Execute initial compaction task
```

Or copy the prompt content and use as system instruction.

**Common Commands:**

| Command | Description |
|---------|-------------|
| `Execute initial compaction task` | First-time setup: creates CHANGELOG.md and TESTS.md |
| `Document fix for [issue]` | Add bug fix entry to CHANGELOG.md |
| `Update test results` | Refresh TESTS.md with latest runs |
| `Review documentation health` | Check line counts and organization |

## Creating New Agents

1. Create `agent-name.md` in this directory
2. Follow the structure:
   - Identity
   - Core Mission
   - Files Under Management
   - Rules
   - Tasks
   - Output Format
3. Add entry to this README

## Best Practices

- Agents should have **single responsibility**
- Always define **clear boundaries** (which files to touch)
- Include **verification steps** (line counts, health checks)
- Provide **invocation examples**
