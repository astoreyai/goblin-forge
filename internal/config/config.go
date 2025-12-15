package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/viper"
	"gopkg.in/yaml.v3"
)

// Config holds all application configuration
type Config struct {
	General      GeneralConfig      `mapstructure:"general" yaml:"general"`
	Tmux         TmuxConfig         `mapstructure:"tmux" yaml:"tmux"`
	Git          GitConfig          `mapstructure:"git" yaml:"git"`
	Voice        VoiceConfig        `mapstructure:"voice" yaml:"voice"`
	Integrations IntegrationsConfig `mapstructure:"integrations" yaml:"integrations"`

	// Computed paths
	DatabasePath string `mapstructure:"-" yaml:"-"`
	WorktreeBase string `mapstructure:"-" yaml:"-"`
	ConfigPath   string `mapstructure:"-" yaml:"-"`
}

type GeneralConfig struct {
	DefaultAgent        string `mapstructure:"default_agent" yaml:"default_agent"`
	WorktreeBase        string `mapstructure:"worktree_base" yaml:"worktree_base"`
	AutoCleanupDays     int    `mapstructure:"auto_cleanup_days" yaml:"auto_cleanup_days"`
	MaxConcurrentAgents int    `mapstructure:"max_concurrent_agents" yaml:"max_concurrent_agents"`
}

type TmuxConfig struct {
	SocketName   string `mapstructure:"socket_name" yaml:"socket_name"`
	DefaultShell string `mapstructure:"default_shell" yaml:"default_shell"`
	HistoryLimit int    `mapstructure:"history_limit" yaml:"history_limit"`
}

type GitConfig struct {
	BranchPrefix string `mapstructure:"branch_prefix" yaml:"branch_prefix"`
	BranchStyle  string `mapstructure:"branch_style" yaml:"branch_style"`
	AutoFetch    bool   `mapstructure:"auto_fetch" yaml:"auto_fetch"`
	AutoStash    bool   `mapstructure:"auto_stash" yaml:"auto_stash"`
}

type VoiceConfig struct {
	Enabled       bool   `mapstructure:"enabled" yaml:"enabled"`
	Model         string `mapstructure:"model" yaml:"model"`
	Hotkey        string `mapstructure:"hotkey" yaml:"hotkey"`
	Language      string `mapstructure:"language" yaml:"language"`
	WakeWord      string `mapstructure:"wake_word" yaml:"wake_word"`
	FeedbackSound bool   `mapstructure:"feedback_sound" yaml:"feedback_sound"`
}

type IntegrationsConfig struct {
	GitHub GitHubConfig `mapstructure:"github" yaml:"github"`
	Linear LinearConfig `mapstructure:"linear" yaml:"linear"`
	Jira   JiraConfig   `mapstructure:"jira" yaml:"jira"`
}

type GitHubConfig struct {
	Enabled bool `mapstructure:"enabled" yaml:"enabled"`
}

type LinearConfig struct {
	Enabled bool   `mapstructure:"enabled" yaml:"enabled"`
	APIKey  string `mapstructure:"api_key" yaml:"api_key"`
}

type JiraConfig struct {
	Enabled bool   `mapstructure:"enabled" yaml:"enabled"`
	URL     string `mapstructure:"url" yaml:"url"`
	Email   string `mapstructure:"email" yaml:"email"`
	Token   string `mapstructure:"token" yaml:"token"`
}

// GetConfigPath returns the configuration file path
func GetConfigPath(override string) string {
	if override != "" {
		return override
	}

	// Check XDG_CONFIG_HOME
	configHome := os.Getenv("XDG_CONFIG_HOME")
	if configHome == "" {
		home, _ := os.UserHomeDir()
		configHome = filepath.Join(home, ".config")
	}

	return filepath.Join(configHome, "gforge", "config.yaml")
}

// GetDataPath returns the data directory path
func GetDataPath() string {
	dataHome := os.Getenv("XDG_DATA_HOME")
	if dataHome == "" {
		home, _ := os.UserHomeDir()
		dataHome = filepath.Join(home, ".local", "share")
	}
	return filepath.Join(dataHome, "gforge")
}

// Load loads configuration from file
func Load(configFile string) (*Config, error) {
	configPath := GetConfigPath(configFile)

	// Set defaults
	setDefaults()

	// Configure viper
	viper.SetConfigFile(configPath)
	viper.SetConfigType("yaml")

	// Environment variable support
	viper.SetEnvPrefix("GFORGE")
	viper.AutomaticEnv()

	// Read config file if it exists
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			// Only return error if it's not a "file not found" error
			if !os.IsNotExist(err) {
				return nil, fmt.Errorf("error reading config: %w", err)
			}
		}
		// Config file doesn't exist, use defaults
	}

	var cfg Config
	if err := viper.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("error parsing config: %w", err)
	}

	// Set computed paths
	cfg.ConfigPath = configPath
	cfg.DatabasePath = filepath.Join(GetDataPath(), "gforge.db")
	cfg.WorktreeBase = expandPath(cfg.General.WorktreeBase)

	// Ensure directories exist
	if err := ensureDirectories(&cfg); err != nil {
		return nil, err
	}

	return &cfg, nil
}

// setDefaults sets default configuration values
func setDefaults() {
	// General
	viper.SetDefault("general.default_agent", "claude")
	viper.SetDefault("general.worktree_base", "~/.local/share/gforge/worktrees")
	viper.SetDefault("general.auto_cleanup_days", 7)
	viper.SetDefault("general.max_concurrent_agents", 10)

	// Tmux
	viper.SetDefault("tmux.socket_name", "gforge")
	viper.SetDefault("tmux.default_shell", os.Getenv("SHELL"))
	viper.SetDefault("tmux.history_limit", 50000)

	// Git
	viper.SetDefault("git.branch_prefix", "gforge/")
	viper.SetDefault("git.branch_style", "kebab-case")
	viper.SetDefault("git.auto_fetch", true)
	viper.SetDefault("git.auto_stash", true)

	// Voice
	viper.SetDefault("voice.enabled", false)
	viper.SetDefault("voice.model", "small")
	viper.SetDefault("voice.hotkey", "super+shift+g")
	viper.SetDefault("voice.language", "auto")
	viper.SetDefault("voice.wake_word", "")
	viper.SetDefault("voice.feedback_sound", true)

	// Integrations
	viper.SetDefault("integrations.github.enabled", true)
	viper.SetDefault("integrations.linear.enabled", false)
	viper.SetDefault("integrations.jira.enabled", false)
}

// Show displays the current configuration
func Show(cfg *Config) error {
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("error marshaling config: %w", err)
	}

	fmt.Printf("# Configuration file: %s\n\n", cfg.ConfigPath)
	fmt.Println(string(data))
	return nil
}

// Initialize creates a default configuration file
func Initialize() error {
	configPath := GetConfigPath("")

	// Check if file already exists
	if _, err := os.Stat(configPath); err == nil {
		return fmt.Errorf("config file already exists: %s", configPath)
	}

	// Ensure directory exists
	dir := filepath.Dir(configPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	// Create default config
	cfg := &Config{
		General: GeneralConfig{
			DefaultAgent:        "claude",
			WorktreeBase:        "~/.local/share/gforge/worktrees",
			AutoCleanupDays:     7,
			MaxConcurrentAgents: 10,
		},
		Tmux: TmuxConfig{
			SocketName:   "gforge",
			DefaultShell: "$SHELL",
			HistoryLimit: 50000,
		},
		Git: GitConfig{
			BranchPrefix: "gforge/",
			BranchStyle:  "kebab-case",
			AutoFetch:    true,
			AutoStash:    true,
		},
		Voice: VoiceConfig{
			Enabled:       false,
			Model:         "small",
			Hotkey:        "super+shift+g",
			Language:      "auto",
			FeedbackSound: true,
		},
		Integrations: IntegrationsConfig{
			GitHub: GitHubConfig{Enabled: true},
			Linear: LinearConfig{Enabled: false},
			Jira:   JiraConfig{Enabled: false},
		},
	}

	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	header := `# Goblin Forge Configuration
# https://github.com/astoreyai/goblin-forge

`

	if err := os.WriteFile(configPath, []byte(header+string(data)), 0644); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	fmt.Printf("Created config file: %s\n", configPath)
	return nil
}

// expandPath expands ~ to home directory
func expandPath(path string) string {
	if len(path) > 0 && path[0] == '~' {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, path[1:])
	}
	return path
}

// ensureDirectories creates required directories
func ensureDirectories(cfg *Config) error {
	dirs := []string{
		filepath.Dir(cfg.DatabasePath),
		cfg.WorktreeBase,
	}

	for _, dir := range dirs {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return fmt.Errorf("failed to create directory %s: %w", dir, err)
		}
	}

	return nil
}
