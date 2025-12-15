package agents

import (
	"testing"
)

func TestNewRegistry(t *testing.T) {
	r := NewRegistry()
	if r == nil {
		t.Fatal("Registry should not be nil")
	}

	// Check that built-in agents are registered
	agents := r.List()
	if len(agents) == 0 {
		t.Error("Registry should have built-in agents")
	}
}

func TestBuiltinAgents(t *testing.T) {
	r := NewRegistry()

	// Test Claude agent
	claude := r.Get("claude")
	if claude == nil {
		t.Fatal("Claude agent should exist")
	}
	if claude.Command != "claude" {
		t.Errorf("Expected command 'claude', got '%s'", claude.Command)
	}
	if !claude.HasCapability("code") {
		t.Error("Claude should have 'code' capability")
	}
	if !claude.HasCapability("git") {
		t.Error("Claude should have 'git' capability")
	}

	// Test Codex agent
	codex := r.Get("codex")
	if codex == nil {
		t.Fatal("Codex agent should exist")
	}
	if codex.Command != "codex" {
		t.Errorf("Expected command 'codex', got '%s'", codex.Command)
	}

	// Test Gemini agent
	gemini := r.Get("gemini")
	if gemini == nil {
		t.Fatal("Gemini agent should exist")
	}
	if gemini.Command != "gemini" {
		t.Errorf("Expected command 'gemini', got '%s'", gemini.Command)
	}

	// Test Ollama agent
	ollama := r.Get("ollama")
	if ollama == nil {
		t.Fatal("Ollama agent should exist")
	}
	if ollama.Command != "ollama" {
		t.Errorf("Expected command 'ollama', got '%s'", ollama.Command)
	}
	if !ollama.HasCapability("local") {
		t.Error("Ollama should have 'local' capability")
	}
}

func TestAgentVariants(t *testing.T) {
	r := NewRegistry()

	// Test Claude auto-accept variant
	claudeAuto := r.Get("claude-auto")
	if claudeAuto == nil {
		t.Fatal("Claude-auto agent should exist")
	}
	if !claudeAuto.AutoAccept {
		t.Error("Claude-auto should have AutoAccept=true")
	}

	// Verify it has the dangerous flag
	cmd := claudeAuto.GetCommand()
	found := false
	for _, arg := range cmd {
		if arg == "--dangerously-skip-permissions" {
			found = true
			break
		}
	}
	if !found {
		t.Error("Claude-auto should have --dangerously-skip-permissions flag")
	}

	// Test Ollama variants
	ollamaDeepseek := r.Get("ollama-deepseek")
	if ollamaDeepseek == nil {
		t.Fatal("Ollama-deepseek agent should exist")
	}

	ollamaQwen := r.Get("ollama-qwen")
	if ollamaQwen == nil {
		t.Fatal("Ollama-qwen agent should exist")
	}
}

func TestGetNonexistent(t *testing.T) {
	r := NewRegistry()

	agent := r.Get("nonexistent")
	if agent != nil {
		t.Error("Should return nil for nonexistent agent")
	}
}

func TestHasCapability(t *testing.T) {
	agent := &Agent{
		Capabilities: []string{"code", "git", "fs"},
	}

	if !agent.HasCapability("code") {
		t.Error("Should have 'code' capability")
	}
	if !agent.HasCapability("git") {
		t.Error("Should have 'git' capability")
	}
	if agent.HasCapability("web") {
		t.Error("Should not have 'web' capability")
	}
}

func TestGetCommand(t *testing.T) {
	agent := &Agent{
		Command: "test-agent",
		Args:    []string{"--flag", "value"},
	}

	cmd := agent.GetCommand()
	if len(cmd) != 3 {
		t.Errorf("Expected 3 parts, got %d", len(cmd))
	}
	if cmd[0] != "test-agent" {
		t.Errorf("Expected 'test-agent', got '%s'", cmd[0])
	}
	if cmd[1] != "--flag" {
		t.Errorf("Expected '--flag', got '%s'", cmd[1])
	}
}

func TestRegisterCustomAgent(t *testing.T) {
	r := NewRegistry()

	customAgent := &Agent{
		Name:         "custom-agent",
		Command:      "my-custom-agent",
		Args:         []string{"--mode", "code"},
		Description:  "My custom agent",
		Capabilities: []string{"code"},
	}

	r.Register(customAgent)

	retrieved := r.Get("custom-agent")
	if retrieved == nil {
		t.Fatal("Custom agent should be retrievable")
	}
	if retrieved.Command != "my-custom-agent" {
		t.Errorf("Expected 'my-custom-agent', got '%s'", retrieved.Command)
	}
}

func TestScan(t *testing.T) {
	r := NewRegistry()

	// Scan will return whatever agents are actually installed
	// This test just verifies it doesn't crash
	detected := r.Scan()

	// detected may be empty if no agents are installed
	// That's okay for testing
	_ = detected
}

func TestNotInstalled(t *testing.T) {
	r := NewRegistry()

	// With no detected agents, all should be not installed
	detected := []DetectedAgent{}
	notInstalled := r.NotInstalled(detected)

	// Should have at least the base agents
	if len(notInstalled) == 0 {
		t.Error("Should report agents as not installed")
	}

	// With claude detected, it should not be in the list
	detected = []DetectedAgent{
		{Name: "claude", Path: "/usr/bin/claude", Version: "1.0.0"},
	}
	notInstalled = r.NotInstalled(detected)

	for _, name := range notInstalled {
		if name == "claude" {
			t.Error("Claude should not be in not-installed list when detected")
		}
	}
}

func TestAgentInstallHints(t *testing.T) {
	r := NewRegistry()

	// All agents should have install hints
	for _, agent := range r.List() {
		if agent.InstallHint == "" {
			t.Errorf("Agent '%s' should have an install hint", agent.Name)
		}
	}
}

func TestAgentDetection(t *testing.T) {
	r := NewRegistry()

	// All agents should have detection config
	for _, agent := range r.List() {
		if agent.Detection.Binary == "" {
			t.Errorf("Agent '%s' should have a detection binary", agent.Name)
		}
	}
}
