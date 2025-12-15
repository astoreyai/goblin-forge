package agents

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// Adapter wraps an agent with a common interface for execution
type Adapter struct {
	agent   *Agent
	cmd     *exec.Cmd
	running bool
	started time.Time
	ctx     context.Context
	cancel  context.CancelFunc
}

// AdapterConfig contains runtime configuration for an adapter
type AdapterConfig struct {
	WorkDir     string
	Env         map[string]string
	InitialTask string
	Timeout     time.Duration
}

// NewAdapter creates a new agent adapter
func NewAdapter(agent *Agent) *Adapter {
	return &Adapter{
		agent: agent,
	}
}

// Start starts the agent with given configuration
func (a *Adapter) Start(cfg AdapterConfig) error {
	if a.running {
		return fmt.Errorf("agent already running")
	}

	ctx, cancel := context.WithCancel(context.Background())
	a.ctx = ctx
	a.cancel = cancel

	// Build command
	args := a.agent.Args
	cmd := exec.CommandContext(ctx, a.agent.Command, args...)

	// Set working directory
	if cfg.WorkDir != "" {
		cmd.Dir = cfg.WorkDir
	}

	// Build environment
	env := os.Environ()
	for k, v := range a.agent.Env {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}
	for k, v := range cfg.Env {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}
	cmd.Env = env

	a.cmd = cmd
	a.started = time.Now()
	a.running = true

	return nil
}

// Stop stops the running agent
func (a *Adapter) Stop() error {
	if !a.running {
		return nil
	}

	if a.cancel != nil {
		a.cancel()
	}

	a.running = false
	return nil
}

// IsRunning returns whether the agent is running
func (a *Adapter) IsRunning() bool {
	return a.running
}

// Uptime returns how long the agent has been running
func (a *Adapter) Uptime() time.Duration {
	if !a.running {
		return 0
	}
	return time.Since(a.started)
}

// Agent returns the underlying agent definition
func (a *Adapter) Agent() *Agent {
	return a.agent
}

// GetCommandString returns the full command as a string for tmux
func (a *Adapter) GetCommandString() string {
	parts := a.agent.GetCommand()
	return strings.Join(parts, " ")
}

// GetEnvString returns environment variables as shell export commands
func (a *Adapter) GetEnvString() string {
	var exports []string
	for k, v := range a.agent.Env {
		exports = append(exports, fmt.Sprintf("export %s=%s", k, v))
	}
	return strings.Join(exports, " && ")
}

// AgentStatus represents the current status of an agent
type AgentStatus string

const (
	StatusIdle      AgentStatus = "idle"
	StatusStarting  AgentStatus = "starting"
	StatusRunning   AgentStatus = "running"
	StatusPaused    AgentStatus = "paused"
	StatusStopping  AgentStatus = "stopping"
	StatusStopped   AgentStatus = "stopped"
	StatusFailed    AgentStatus = "failed"
	StatusCompleted AgentStatus = "completed"
)

// LifecycleEvent represents an agent lifecycle event
type LifecycleEvent struct {
	Type      string
	AgentName string
	GoblinID  string
	Timestamp time.Time
	Details   map[string]string
}

// LifecycleManager handles agent lifecycle events
type LifecycleManager struct {
	events   []LifecycleEvent
	handlers []func(LifecycleEvent)
}

// NewLifecycleManager creates a new lifecycle manager
func NewLifecycleManager() *LifecycleManager {
	return &LifecycleManager{
		events:   make([]LifecycleEvent, 0),
		handlers: make([]func(LifecycleEvent), 0),
	}
}

// OnEvent registers a handler for lifecycle events
func (lm *LifecycleManager) OnEvent(handler func(LifecycleEvent)) {
	lm.handlers = append(lm.handlers, handler)
}

// Emit emits a lifecycle event
func (lm *LifecycleManager) Emit(event LifecycleEvent) {
	event.Timestamp = time.Now()
	lm.events = append(lm.events, event)

	for _, h := range lm.handlers {
		go h(event)
	}
}

// RecentEvents returns recent lifecycle events
func (lm *LifecycleManager) RecentEvents(limit int) []LifecycleEvent {
	if len(lm.events) <= limit {
		return lm.events
	}
	return lm.events[len(lm.events)-limit:]
}

// HealthChecker monitors agent health
type HealthChecker struct {
	checkInterval time.Duration
	checkFunc     func(string) bool
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(interval time.Duration, checker func(string) bool) *HealthChecker {
	return &HealthChecker{
		checkInterval: interval,
		checkFunc:     checker,
	}
}

// Check performs a health check
func (hc *HealthChecker) Check(sessionName string) bool {
	if hc.checkFunc == nil {
		return true
	}
	return hc.checkFunc(sessionName)
}

// GetCheckInterval returns the check interval
func (hc *HealthChecker) GetCheckInterval() time.Duration {
	return hc.checkInterval
}
