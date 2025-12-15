package agents

import (
	"testing"
	"time"
)

func TestNewAdapter(t *testing.T) {
	agent := &Agent{
		Name:    "test-agent",
		Command: "echo",
		Args:    []string{"hello"},
	}

	adapter := NewAdapter(agent)
	if adapter == nil {
		t.Fatal("Adapter should not be nil")
	}

	if adapter.Agent() != agent {
		t.Error("Agent should match")
	}

	if adapter.IsRunning() {
		t.Error("Adapter should not be running initially")
	}
}

func TestAdapterCommandString(t *testing.T) {
	agent := &Agent{
		Name:    "test-agent",
		Command: "claude",
		Args:    []string{"--dangerously-skip-permissions"},
	}

	adapter := NewAdapter(agent)
	cmdStr := adapter.GetCommandString()

	expected := "claude --dangerously-skip-permissions"
	if cmdStr != expected {
		t.Errorf("Expected '%s', got '%s'", expected, cmdStr)
	}
}

func TestAdapterEnvString(t *testing.T) {
	agent := &Agent{
		Name:    "test-agent",
		Command: "ollama",
		Env: map[string]string{
			"OLLAMA_HOST": "127.0.0.1:11434",
		},
	}

	adapter := NewAdapter(agent)
	envStr := adapter.GetEnvString()

	if envStr == "" {
		t.Error("Env string should not be empty")
	}
}

func TestAdapterStart(t *testing.T) {
	agent := &Agent{
		Name:    "test-agent",
		Command: "echo",
		Args:    []string{"hello"},
	}

	adapter := NewAdapter(agent)
	err := adapter.Start(AdapterConfig{
		WorkDir: "/tmp",
	})

	if err != nil {
		t.Fatalf("Start should not error: %v", err)
	}

	if !adapter.IsRunning() {
		t.Error("Adapter should be running after Start")
	}

	// Can't start twice
	err = adapter.Start(AdapterConfig{})
	if err == nil {
		t.Error("Should error when starting twice")
	}
}

func TestAdapterStop(t *testing.T) {
	agent := &Agent{
		Name:    "test-agent",
		Command: "echo",
		Args:    []string{"hello"},
	}

	adapter := NewAdapter(agent)
	adapter.Start(AdapterConfig{})
	adapter.Stop()

	if adapter.IsRunning() {
		t.Error("Adapter should not be running after Stop")
	}
}

func TestAdapterUptime(t *testing.T) {
	agent := &Agent{
		Name:    "test-agent",
		Command: "sleep",
		Args:    []string{"1"},
	}

	adapter := NewAdapter(agent)

	// Not running
	if adapter.Uptime() != 0 {
		t.Error("Uptime should be 0 when not running")
	}

	adapter.Start(AdapterConfig{})
	time.Sleep(10 * time.Millisecond)

	uptime := adapter.Uptime()
	if uptime < 10*time.Millisecond {
		t.Error("Uptime should be at least 10ms")
	}

	adapter.Stop()
}

func TestAgentStatus(t *testing.T) {
	tests := []struct {
		status AgentStatus
		str    string
	}{
		{StatusIdle, "idle"},
		{StatusStarting, "starting"},
		{StatusRunning, "running"},
		{StatusPaused, "paused"},
		{StatusStopping, "stopping"},
		{StatusStopped, "stopped"},
		{StatusFailed, "failed"},
		{StatusCompleted, "completed"},
	}

	for _, tc := range tests {
		if string(tc.status) != tc.str {
			t.Errorf("Expected '%s', got '%s'", tc.str, string(tc.status))
		}
	}
}

func TestLifecycleManager(t *testing.T) {
	lm := NewLifecycleManager()

	// Register handler
	var received *LifecycleEvent
	lm.OnEvent(func(e LifecycleEvent) {
		received = &e
	})

	// Emit event
	lm.Emit(LifecycleEvent{
		Type:      "spawn",
		AgentName: "claude",
		GoblinID:  "test-123",
		Details: map[string]string{
			"branch": "gforge/test",
		},
	})

	// Give handler time to run
	time.Sleep(10 * time.Millisecond)

	if received == nil {
		t.Fatal("Handler should have received event")
	}

	if received.Type != "spawn" {
		t.Errorf("Expected type 'spawn', got '%s'", received.Type)
	}

	if received.AgentName != "claude" {
		t.Errorf("Expected agent 'claude', got '%s'", received.AgentName)
	}
}

func TestLifecycleManagerRecentEvents(t *testing.T) {
	lm := NewLifecycleManager()

	// Emit multiple events
	for i := 0; i < 10; i++ {
		lm.Emit(LifecycleEvent{
			Type:      "test",
			AgentName: "agent",
			GoblinID:  "id",
		})
	}

	// Get recent events
	events := lm.RecentEvents(5)
	if len(events) != 5 {
		t.Errorf("Expected 5 events, got %d", len(events))
	}

	// Get all events
	events = lm.RecentEvents(100)
	if len(events) != 10 {
		t.Errorf("Expected 10 events, got %d", len(events))
	}
}

func TestHealthChecker(t *testing.T) {
	checkedSessions := make(map[string]bool)

	hc := NewHealthChecker(5*time.Second, func(session string) bool {
		checkedSessions[session] = true
		return true
	})

	if hc.GetCheckInterval() != 5*time.Second {
		t.Error("Check interval mismatch")
	}

	result := hc.Check("test-session")
	if !result {
		t.Error("Check should return true")
	}

	if !checkedSessions["test-session"] {
		t.Error("Session should have been checked")
	}
}

func TestHealthCheckerNilFunc(t *testing.T) {
	hc := NewHealthChecker(5*time.Second, nil)

	// Should return true when no checker function
	result := hc.Check("test-session")
	if !result {
		t.Error("Check should return true when no checker func")
	}
}
