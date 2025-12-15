# Goblin Forge

> "Where code is forged by many small minds."

**Goblin Forge** (`gforge`) is a multi-agent command-line orchestrator designed to coordinate and execute multiple coding-focused CLI agents in parallel.

```
     ╔═══════════════════════════════════════════════════════════════╗
     ║                                                               ║
     ║   ░██████╗░░█████╗░██████╗░██╗░░░░░██╗███╗░░██╗               ║
     ║   ██╔════╝░██╔══██╗██╔══██╗██║░░░░░██║████╗░██║               ║
     ║   ██║░░██╗░██║░░██║██████╦╝██║░░░░░██║██╔██╗██║               ║
     ║   ██║░░╚██╗██║░░██║██╔══██╗██║░░░░░██║██║╚████║               ║
     ║   ╚██████╔╝╚█████╔╝██████╦╝███████╗██║██║░╚███║               ║
     ║   ░╚═════╝░░╚════╝░╚═════╝░╚══════╝╚═╝╚═╝░░╚══╝               ║
     ║                                                               ║
     ║   ███████╗░█████╗░██████╗░░██████╗░███████╗                   ║
     ║   ██╔════╝██╔══██╗██╔══██╗██╔════╝░██╔════╝                   ║
     ║   █████╗░░██║░░██║██████╔╝██║░░██╗░█████╗░░                   ║
     ║   ██╔══╝░░██║░░██║██╔══██╗██║░░╚██╗██╔══╝░░                   ║
     ║   ██║░░░░░╚█████╔╝██║░░██║╚██████╔╝███████╗                   ║
     ║   ╚═╝░░░░░░╚════╝░╚═╝░░╚═╝░╚═════╝░╚══════╝                   ║
     ║                                                               ║
     ║           Multi-Agent CLI Orchestrator for Linux              ║
     ║                                                               ║
     ╚═══════════════════════════════════════════════════════════════╝
```

## Status: Phase 1 Complete

- [x] CLI framework (Cobra)
- [x] Configuration system (Viper + YAML)
- [x] SQLite storage layer
- [x] Agent registry (Claude, Codex, Gemini, Ollama)
- [x] Basic spawn/list/stop commands
- [ ] tmux session management (Phase 2)
- [ ] TUI dashboard (Phase 4)
- [ ] Voice control (Phase 6)

## Quick Start

```bash
# Build
make build

# Or install locally
make install

# Check version
gforge version

# Initialize config
gforge config init

# Scan for installed agents
gforge agents scan

# List available agents
gforge agents list

# Spawn a goblin (agent instance)
gforge spawn coder --agent claude --project ./my-app

# List active goblins
gforge list

# Stop a goblin
gforge stop coder
```

## Supported Agents

| Agent | Command | Description |
|-------|---------|-------------|
| **Claude Code** | `claude` | Anthropic Claude Code CLI |
| **Codex** | `codex` | OpenAI Codex CLI |
| **Gemini** | `gemini` | Google Gemini CLI |
| **Ollama** | `ollama` | Local LLMs (CodeLlama, DeepSeek, Qwen) |

## Project Structure

```
goblin-forge/
├── cmd/gforge/           # CLI entrypoint
├── internal/
│   ├── agents/           # Agent definitions and registry
│   ├── config/           # Configuration management
│   ├── coordinator/      # Goblin lifecycle management
│   ├── logging/          # Structured logging
│   └── storage/          # SQLite persistence
├── configs/              # Default configuration files
├── CLAUDE.md             # Full architecture documentation
├── IMPLEMENTATION_PLAN.md # 8-phase roadmap
└── Makefile
```

## Development

```bash
# Download dependencies
make deps

# Run tests
make test

# Run with coverage
make coverage

# Format code
make fmt

# Run linter
make lint

# Build for all platforms
make build-all
```

## Configuration

Config file: `~/.config/gforge/config.yaml`

```yaml
general:
  default_agent: claude
  worktree_base: ~/.local/share/gforge/worktrees

tmux:
  socket_name: gforge

git:
  branch_prefix: "gforge/"
  branch_style: kebab-case
```

## Documentation

- **[CLAUDE.md](./CLAUDE.md)** - Full architecture and CLI reference
- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** - 8-phase roadmap with deliverables

## License

Apache-2.0
