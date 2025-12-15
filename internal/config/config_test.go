package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestGetConfigPath(t *testing.T) {
	// Test with override
	override := "/custom/path/config.yaml"
	result := GetConfigPath(override)
	if result != override {
		t.Errorf("Expected '%s', got '%s'", override, result)
	}

	// Test without override (should use default)
	result = GetConfigPath("")
	if result == "" {
		t.Error("Should return default config path")
	}

	// Should end with config.yaml
	if filepath.Base(result) != "config.yaml" {
		t.Errorf("Expected 'config.yaml', got '%s'", filepath.Base(result))
	}
}

func TestGetDataPath(t *testing.T) {
	path := GetDataPath()
	if path == "" {
		t.Error("Data path should not be empty")
	}

	// Should end with gforge
	if filepath.Base(path) != "gforge" {
		t.Errorf("Expected 'gforge', got '%s'", filepath.Base(path))
	}
}

func TestLoadDefaults(t *testing.T) {
	// Create temp directory
	tmpDir, err := os.MkdirTemp("", "gforge-config-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Set XDG dirs to temp
	os.Setenv("XDG_CONFIG_HOME", tmpDir)
	os.Setenv("XDG_DATA_HOME", tmpDir)
	defer func() {
		os.Unsetenv("XDG_CONFIG_HOME")
		os.Unsetenv("XDG_DATA_HOME")
	}()

	// Load config (should use defaults since no file exists)
	cfg, err := Load("")
	if err != nil {
		t.Fatalf("Failed to load config: %v", err)
	}

	// Check default values
	if cfg.General.DefaultAgent != "claude" {
		t.Errorf("Expected default agent 'claude', got '%s'", cfg.General.DefaultAgent)
	}

	if cfg.General.AutoCleanupDays != 7 {
		t.Errorf("Expected auto_cleanup_days 7, got %d", cfg.General.AutoCleanupDays)
	}

	if cfg.Tmux.SocketName != "gforge" {
		t.Errorf("Expected socket name 'gforge', got '%s'", cfg.Tmux.SocketName)
	}

	if cfg.Git.BranchPrefix != "gforge/" {
		t.Errorf("Expected branch prefix 'gforge/', got '%s'", cfg.Git.BranchPrefix)
	}

	if cfg.Voice.Model != "small" {
		t.Errorf("Expected voice model 'small', got '%s'", cfg.Voice.Model)
	}
}

func TestInitialize(t *testing.T) {
	// Create temp directory
	tmpDir, err := os.MkdirTemp("", "gforge-config-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Set XDG dir to temp
	os.Setenv("XDG_CONFIG_HOME", tmpDir)
	defer os.Unsetenv("XDG_CONFIG_HOME")

	// Initialize config
	err = Initialize()
	if err != nil {
		t.Fatalf("Failed to initialize config: %v", err)
	}

	// Check file was created
	configPath := filepath.Join(tmpDir, "gforge", "config.yaml")
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		t.Error("Config file should have been created")
	}

	// Try to initialize again - should fail
	err = Initialize()
	if err == nil {
		t.Error("Should fail when config already exists")
	}
}

func TestExpandPath(t *testing.T) {
	home, _ := os.UserHomeDir()

	tests := []struct {
		input    string
		expected string
	}{
		{"~/test", filepath.Join(home, "test")},
		{"/absolute/path", "/absolute/path"},
		{"relative/path", "relative/path"},
	}

	for _, tc := range tests {
		result := expandPath(tc.input)
		if result != tc.expected {
			t.Errorf("expandPath(%s): expected '%s', got '%s'", tc.input, tc.expected, result)
		}
	}
}

func TestConfigShow(t *testing.T) {
	cfg := &Config{
		General: GeneralConfig{
			DefaultAgent:    "claude",
			AutoCleanupDays: 7,
		},
		Tmux: TmuxConfig{
			SocketName: "gforge",
		},
		ConfigPath: "/test/path",
	}

	// Should not panic
	err := Show(cfg)
	if err != nil {
		t.Errorf("Show should not error: %v", err)
	}
}

func TestEnsureDirectories(t *testing.T) {
	// Create temp directory
	tmpDir, err := os.MkdirTemp("", "gforge-config-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	cfg := &Config{
		DatabasePath: filepath.Join(tmpDir, "data", "gforge.db"),
		WorktreeBase: filepath.Join(tmpDir, "worktrees"),
	}

	err = ensureDirectories(cfg)
	if err != nil {
		t.Fatalf("Failed to ensure directories: %v", err)
	}

	// Check directories were created
	if _, err := os.Stat(filepath.Join(tmpDir, "data")); os.IsNotExist(err) {
		t.Error("Data directory should have been created")
	}
	if _, err := os.Stat(filepath.Join(tmpDir, "worktrees")); os.IsNotExist(err) {
		t.Error("Worktrees directory should have been created")
	}
}

func TestConfigIntegrations(t *testing.T) {
	cfg := &Config{
		Integrations: IntegrationsConfig{
			GitHub: GitHubConfig{Enabled: true},
			Linear: LinearConfig{Enabled: false, APIKey: "test-key"},
			Jira:   JiraConfig{Enabled: false, URL: "https://test.atlassian.net"},
		},
	}

	if !cfg.Integrations.GitHub.Enabled {
		t.Error("GitHub should be enabled")
	}
	if cfg.Integrations.Linear.Enabled {
		t.Error("Linear should be disabled")
	}
	if cfg.Integrations.Linear.APIKey != "test-key" {
		t.Error("Linear API key should be set")
	}
}
