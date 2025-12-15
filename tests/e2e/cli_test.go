package e2e

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// E2E tests for the gforge CLI
// These tests build and run the actual CLI binary

var binaryPath string

func TestMain(m *testing.M) {
	// Build the binary before running tests
	tmpDir, err := os.MkdirTemp("", "gforge-e2e-bin-*")
	if err != nil {
		panic(err)
	}

	binaryPath = filepath.Join(tmpDir, "gforge")

	// Build from project root
	projectRoot := findProjectRoot()
	cmd := exec.Command("go", "build", "-o", binaryPath, "./cmd/gforge")
	cmd.Dir = projectRoot

	output, err := cmd.CombinedOutput()
	if err != nil {
		panic("Failed to build binary: " + err.Error() + "\n" + string(output))
	}

	// Run tests
	code := m.Run()

	// Cleanup
	os.RemoveAll(tmpDir)
	os.Exit(code)
}

func findProjectRoot() string {
	// Start from current dir and walk up until we find go.mod
	dir, _ := os.Getwd()
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			// Reached root, use relative path
			return "../.."
		}
		dir = parent
	}
}

func runCLI(args ...string) (string, string, error) {
	cmd := exec.Command(binaryPath, args...)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	return stdout.String(), stderr.String(), err
}

func TestCLIVersion(t *testing.T) {
	stdout, _, err := runCLI("version")
	if err != nil {
		t.Fatalf("version command failed: %v", err)
	}

	if !strings.Contains(stdout, "Goblin Forge") {
		t.Errorf("Expected 'Goblin Forge' in output, got: %s", stdout)
	}
}

func TestCLIHelp(t *testing.T) {
	stdout, _, err := runCLI("--help")
	if err != nil {
		t.Fatalf("help command failed: %v", err)
	}

	// Check for expected commands
	expectedCommands := []string{
		"spawn",
		"list",
		"stop",
		"kill",
		"attach",
		"logs",
		"diff",
		"status",
		"agents",
		"config",
	}

	for _, cmd := range expectedCommands {
		if !strings.Contains(stdout, cmd) {
			t.Errorf("Expected command '%s' in help output", cmd)
		}
	}
}

func TestCLIAgentsList(t *testing.T) {
	stdout, _, err := runCLI("agents", "list")
	if err != nil {
		t.Fatalf("agents list failed: %v", err)
	}

	// Should list available agents
	if !strings.Contains(stdout, "Available Agents") {
		t.Error("Expected 'Available Agents' header")
	}

	// Should include built-in agents
	agents := []string{"claude", "codex", "gemini", "ollama"}
	for _, agent := range agents {
		if !strings.Contains(stdout, agent) {
			t.Errorf("Expected agent '%s' in list", agent)
		}
	}
}

func TestCLIAgentsScan(t *testing.T) {
	stdout, _, err := runCLI("agents", "scan")
	// Scan should work even if no agents installed
	if err != nil {
		t.Fatalf("agents scan failed: %v", err)
	}

	if !strings.Contains(stdout, "Scanning for installed agents") {
		t.Error("Expected scanning message")
	}
}

func TestCLIConfigPath(t *testing.T) {
	stdout, _, err := runCLI("config", "path")
	if err != nil {
		t.Fatalf("config path failed: %v", err)
	}

	// Should output a path
	if !strings.Contains(stdout, "config") || !strings.Contains(stdout, "gforge") {
		t.Errorf("Expected config path, got: %s", stdout)
	}
}

func TestCLIListEmpty(t *testing.T) {
	// Create temp dir for isolated database
	tmpDir, err := os.MkdirTemp("", "gforge-e2e-list-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Run with custom config pointing to temp dir
	configPath := filepath.Join(tmpDir, "config.yaml")
	os.WriteFile(configPath, []byte(`
general:
  auto_accept: false
database_path: `+filepath.Join(tmpDir, "gforge.db")+`
worktree_base: `+filepath.Join(tmpDir, "worktrees")+`
`), 0644)

	stdout, _, err := runCLI("--config", configPath, "list")
	if err != nil {
		t.Fatalf("list command failed: %v", err)
	}

	if !strings.Contains(stdout, "No active goblins") {
		t.Errorf("Expected 'No active goblins', got: %s", stdout)
	}
}

func TestCLIStatusEmpty(t *testing.T) {
	// Create temp dir for isolated database
	tmpDir, err := os.MkdirTemp("", "gforge-e2e-status-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	configPath := filepath.Join(tmpDir, "config.yaml")
	os.WriteFile(configPath, []byte(`
general:
  auto_accept: false
database_path: `+filepath.Join(tmpDir, "gforge.db")+`
worktree_base: `+filepath.Join(tmpDir, "worktrees")+`
`), 0644)

	stdout, _, err := runCLI("--config", configPath, "status")
	if err != nil {
		t.Fatalf("status command failed: %v", err)
	}

	if !strings.Contains(stdout, "Goblin Forge Status") {
		t.Errorf("Expected status header, got: %s", stdout)
	}
}

func TestCLISpawnMissingArgs(t *testing.T) {
	_, stderr, err := runCLI("spawn")
	if err == nil {
		t.Error("spawn without args should fail")
	}

	if !strings.Contains(stderr, "accepts 1 arg") {
		t.Errorf("Expected args error, got: %s", stderr)
	}
}

func TestCLIStopMissingArgs(t *testing.T) {
	_, stderr, err := runCLI("stop")
	if err == nil {
		t.Error("stop without args should fail")
	}

	if !strings.Contains(stderr, "accepts 1 arg") {
		t.Errorf("Expected args error, got: %s", stderr)
	}
}

func TestCLIKillMissingArgs(t *testing.T) {
	_, stderr, err := runCLI("kill")
	if err == nil {
		t.Error("kill without args should fail")
	}

	if !strings.Contains(stderr, "accepts 1 arg") {
		t.Errorf("Expected args error, got: %s", stderr)
	}
}

func TestCLIDiffMissingArgs(t *testing.T) {
	_, stderr, err := runCLI("diff")
	if err == nil {
		t.Error("diff without args should fail")
	}

	if !strings.Contains(stderr, "accepts 1 arg") {
		t.Errorf("Expected args error, got: %s", stderr)
	}
}

func TestCLILogsMissingArgs(t *testing.T) {
	_, stderr, err := runCLI("logs")
	if err == nil {
		t.Error("logs without args should fail")
	}

	if !strings.Contains(stderr, "accepts 1 arg") {
		t.Errorf("Expected args error, got: %s", stderr)
	}
}

func TestCLIAttachMissingArgs(t *testing.T) {
	_, stderr, err := runCLI("attach")
	if err == nil {
		t.Error("attach without args should fail")
	}

	if !strings.Contains(stderr, "accepts 1 arg") {
		t.Errorf("Expected args error, got: %s", stderr)
	}
}

func TestCLITaskMissingGoblin(t *testing.T) {
	_, stderr, err := runCLI("task", "do something")
	if err == nil {
		t.Error("task without --goblin should fail")
	}

	if !strings.Contains(stderr, "required flag") || !strings.Contains(stderr, "goblin") {
		t.Errorf("Expected required flag error, got: %s", stderr)
	}
}

// Integration-style E2E test for full workflow
func TestCLIFullWorkflow(t *testing.T) {
	// Skip if git/tmux not available
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not available")
	}
	if _, err := exec.LookPath("tmux"); err != nil {
		t.Skip("tmux not available")
	}

	// Setup test environment
	tmpDir, err := os.MkdirTemp("", "gforge-e2e-workflow-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Create test repo
	repoDir := filepath.Join(tmpDir, "repo")
	os.MkdirAll(repoDir, 0755)
	exec.Command("git", "init", repoDir).Run()
	exec.Command("git", "-C", repoDir, "config", "user.email", "test@test.com").Run()
	exec.Command("git", "-C", repoDir, "config", "user.name", "Test").Run()
	os.WriteFile(filepath.Join(repoDir, "README.md"), []byte("# Test\n"), 0644)
	exec.Command("git", "-C", repoDir, "add", ".").Run()
	exec.Command("git", "-C", repoDir, "commit", "-m", "Initial").Run()

	// Create config
	configPath := filepath.Join(tmpDir, "config.yaml")
	os.WriteFile(configPath, []byte(`
general:
  auto_accept: false
database_path: `+filepath.Join(tmpDir, "gforge.db")+`
worktree_base: `+filepath.Join(tmpDir, "worktrees")+`
tmux:
  socket_name: gforge-e2e-workflow
`), 0644)

	// Cleanup tmux after test
	defer exec.Command("tmux", "-L", "gforge-e2e-workflow", "kill-server").Run()

	// Test spawn - use echo agent (always available)
	t.Run("Spawn", func(t *testing.T) {
		stdout, stderr, err := runCLI(
			"--config", configPath,
			"spawn", "e2e-test",
			"--project", repoDir,
			"--branch", "gforge/e2e-test",
		)
		if err != nil {
			t.Fatalf("spawn failed: %v\nstdout: %s\nstderr: %s", err, stdout, stderr)
		}

		if !strings.Contains(stdout, "Spawned goblin") {
			t.Errorf("Expected success message, got: %s", stdout)
		}
	})

	// Test list
	t.Run("List", func(t *testing.T) {
		stdout, _, err := runCLI("--config", configPath, "list")
		if err != nil {
			t.Fatalf("list failed: %v", err)
		}

		if !strings.Contains(stdout, "e2e-test") {
			t.Errorf("Expected goblin in list, got: %s", stdout)
		}
	})

	// Test status
	t.Run("Status", func(t *testing.T) {
		stdout, _, err := runCLI("--config", configPath, "status")
		if err != nil {
			t.Fatalf("status failed: %v", err)
		}

		if !strings.Contains(stdout, "Running:") {
			t.Errorf("Expected running count, got: %s", stdout)
		}
	})

	// Test kill
	t.Run("Kill", func(t *testing.T) {
		stdout, _, err := runCLI("--config", configPath, "kill", "e2e-test")
		if err != nil {
			t.Fatalf("kill failed: %v", err)
		}

		if !strings.Contains(stdout, "Killed goblin") {
			t.Errorf("Expected kill message, got: %s", stdout)
		}
	})

	// Verify gone
	t.Run("VerifyGone", func(t *testing.T) {
		stdout, _, _ := runCLI("--config", configPath, "list")
		if strings.Contains(stdout, "e2e-test") {
			t.Error("Goblin should be gone after kill")
		}
	})
}
