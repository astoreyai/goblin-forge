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

## Status: v1.0.0 Complete

All 8 phases implemented:

- [x] Phase 1: Foundation (CLI, Config, Storage)
- [x] Phase 2: Isolation Layer (tmux, git worktrees)
- [x] Phase 3: Agent System (Registry, Adapters)
- [x] Phase 4: TUI Dashboard (Bubble Tea)
- [x] Phase 5: Template System (40+ templates)
- [x] Phase 6: Voice Control (Whisper STT)
- [x] Phase 7: Integrations (GitHub, Linear, Jira)
- [x] Phase 8: Polish & Release

## Features

- **Multi-Agent Orchestration**: Run Claude, Aider, Codex, and other AI agents simultaneously
- **Complete Isolation**: Each "goblin" gets its own tmux session and git worktree
- **TUI Dashboard**: htop-like interface for monitoring and managing goblins
- **Voice Control**: Speak commands using Whisper STT (local, no cloud)
- **Template System**: 40+ project templates with auto-detection
- **Integrations**: GitHub, Linear, Jira for issue import and PR creation
- **Editor Support**: Launch VS Code, Vim, Emacs directly to goblin worktrees

## Quick Start

```bash
# Build
make build

# Or install locally
make install

# Check version
gforge version

# Scan for installed agents
gforge agents scan

# Spawn a goblin (agent instance)
gforge spawn coder --agent claude --project ./my-app

# List active goblins
gforge list

# Attach to a goblin
gforge attach coder

# Launch dashboard
gforge top
```

## Installation

### Requirements

- Linux (primary platform)
- Go 1.22+ (for building from source)
- tmux (for session isolation)
- git (for worktree isolation)
- One or more AI coding CLIs (claude, aider, etc.)

### Build from Source

```bash
git clone https://github.com/astoreyai/goblin-forge.git
cd goblin-forge
make install
```

## Usage

### Basic Commands

```bash
# Spawn a new goblin
gforge spawn <name> --agent <agent> [--project <path>] [--branch <name>]

# List all goblins
gforge list

# Attach to a goblin's tmux session
gforge attach <name>

# View goblin output
gforge logs <name>

# Show changes made by a goblin
gforge diff <name>

# Stop a goblin gracefully
gforge stop <name>

# Kill a goblin forcefully
gforge kill <name>

# Launch TUI dashboard
gforge top
```

### Working with Issues

```bash
# Spawn from GitHub issue
gforge spawn coder --from-issue gh:owner/repo#123

# Spawn from Linear ticket
gforge spawn coder --from-issue linear:PROJ-456

# Spawn from Jira issue
gforge spawn coder --from-issue jira:PROJ-789
```

### Voice Control

```bash
# Start voice daemon (requires faster-whisper)
gforge voice start

# Voice commands:
#   "Spawn coder with agent Claude"
#   "Attach to goblin reviewer"
#   "Show diff for tester"
#   "List all goblins"
```

### Templates

```bash
# List available templates
gforge templates list

# Auto-detect project type
gforge templates detect
```

40+ templates included: Node.js, Python, Rust, Go, Ruby, Elixir, Java, .NET, and frameworks like Next.js, FastAPI, Django, Rails, Phoenix.

## TUI Dashboard

Launch with `gforge top`:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GOBLIN FORGE v1.0.0                              🎤 Voice: OFF   q: quit  │
├─────────────────────────────────────────────────────────────────────────────┤
│  GOBLINS (3)                           │  OUTPUT: coder [Claude]           │
│  ────────────────────────────────────  │  ─────────────────────────────────│
│  ▶ 1. coder        [Claude]   RUNNING  │  Analyzing the authentication     │
│    2. reviewer     [Aider]    PAUSED   │  module for potential issues...   │
│    3. tester       [Codex]    IDLE     │                                   │
│                                                                             │
│  n:spawn  a:attach  d:diff  k:kill  p:pause  r:resume  tab:switch  ?:help │
└─────────────────────────────────────────────────────────────────────────────┘
```

Keybindings:
- `j/k`, `↑/↓` - Navigate goblin list
- `a`, `Enter` - Attach to selected goblin
- `s` - Stop selected goblin
- `K` (Shift+K) - Kill selected goblin
- `d` - Show diff
- `?` - Show help
- `q` - Quit

## Supported Agents

| Agent | Command | Description |
|-------|---------|-------------|
| **Claude Code** | `claude` | Anthropic Claude Code CLI |
| **Aider** | `aider` | AI pair programming |
| **Codex** | `codex` | OpenAI Codex CLI |
| **Gemini** | `gemini` | Google Gemini CLI |
| **Ollama** | `ollama` | Local LLMs (CodeLlama, DeepSeek, Qwen) |
| **Custom** | Any CLI | Via generic adapter |

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

voice:
  model: tiny  # tiny, base, small, medium, large
  device: auto # cpu, cuda, auto
  hotkey: KEY_SCROLLLOCK
```

## Project Structure

```
goblin-forge/
├── cmd/gforge/           # CLI entrypoint
├── internal/
│   ├── agents/           # Agent definitions and registry
│   ├── config/           # Configuration management
│   ├── coordinator/      # Goblin lifecycle management
│   ├── integrations/     # GitHub, Linear, Jira, Editor
│   ├── ipc/              # Voice daemon IPC
│   ├── logging/          # Structured logging
│   ├── storage/          # SQLite persistence
│   ├── template/         # Template engine
│   ├── tmux/             # Session management
│   ├── tui/              # Bubble Tea dashboard
│   └── workspace/        # Git worktree management
├── templates/builtin/    # 40+ project templates
├── voice/                # Python voice daemon
├── CLAUDE.md             # Architecture documentation
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

## Documentation

- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** - 8-phase roadmap with deliverables
- **[CHARM_VS_GOBLINFORGE_ANALYSIS.md](./CHARM_VS_GOBLINFORGE_ANALYSIS.md)** - Architecture comparison

## License

Apache-2.0
