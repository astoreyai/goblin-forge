package integration

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/astoreyai/goblin-forge/internal/agents"
	"github.com/astoreyai/goblin-forge/internal/config"
	"github.com/astoreyai/goblin-forge/internal/coordinator"
	"github.com/astoreyai/goblin-forge/internal/logging"
	"github.com/astoreyai/goblin-forge/internal/storage"
	"github.com/astoreyai/goblin-forge/internal/tmux"
	"github.com/astoreyai/goblin-forge/internal/workspace"
)

// Integration tests for the full spawn workflow
// These tests verify that all components work together correctly

func skipIfNoGit(t *testing.T) {
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not available")
	}
}

func skipIfNoTmux(t *testing.T) {
	if _, err := exec.LookPath("tmux"); err != nil {
		t.Skip("tmux not available")
	}
}

// TestSpawnWorkflow tests the complete spawn workflow
func TestSpawnWorkflow(t *testing.T) {
	skipIfNoGit(t)
	skipIfNoTmux(t)

	// Setup
	tmpDir, err := os.MkdirTemp("", "gforge-integration-*")
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
	exec.Command("git", "-C", repoDir, "commit", "-m", "Initial commit").Run()

	// Setup components
	dbPath := filepath.Join(tmpDir, "gforge.db")
	db, err := storage.New(dbPath)
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	cfg := &config.Config{
		DatabasePath: dbPath,
		WorktreeBase: filepath.Join(tmpDir, "worktrees"),
		Tmux: config.TmuxConfig{
			SocketName: "gforge-integ-test",
		},
	}
	os.MkdirAll(cfg.WorktreeBase, 0755)

	log := logging.New(false)
	coord := coordinator.New(db, cfg, log)

	// Cleanup tmux after test
	defer exec.Command("tmux", "-L", "gforge-integ-test", "kill-server").Run()

	// Define test agent
	agent := &agents.Agent{
		Name:    "shell",
		Command: "bash",
		Args:    []string{},
	}

	// === Test Spawn ===
	t.Run("Spawn", func(t *testing.T) {
		goblin, err := coord.Spawn(coordinator.SpawnOptions{
			Name:        "integ-test",
			Agent:       agent,
			ProjectPath: repoDir,
			Branch:      "gforge/integ-test",
		})
		if err != nil {
			t.Fatalf("Spawn failed: %v", err)
		}

		if goblin.Name != "integ-test" {
			t.Errorf("Expected name 'integ-test', got '%s'", goblin.Name)
		}

		if goblin.Branch != "gforge/integ-test" {
			t.Errorf("Expected branch 'gforge/integ-test', got '%s'", goblin.Branch)
		}

		// Verify worktree exists
		if _, err := os.Stat(goblin.WorktreePath); os.IsNotExist(err) {
			t.Error("Worktree should exist")
		}
	})

	// === Test Get ===
	t.Run("Get", func(t *testing.T) {
		goblin, err := coord.Get("integ-test")
		if err != nil {
			t.Fatalf("Get failed: %v", err)
		}
		if goblin == nil {
			t.Fatal("Goblin should exist")
		}
	})

	// === Test List ===
	t.Run("List", func(t *testing.T) {
		goblins, err := coord.List()
		if err != nil {
			t.Fatalf("List failed: %v", err)
		}
		if len(goblins) != 1 {
			t.Errorf("Expected 1 goblin, got %d", len(goblins))
		}
	})

	// === Test Stats ===
	t.Run("Stats", func(t *testing.T) {
		stats, err := coord.Stats()
		if err != nil {
			t.Fatalf("Stats failed: %v", err)
		}
		if stats.Total != 1 {
			t.Errorf("Expected total 1, got %d", stats.Total)
		}
		if stats.Running != 1 {
			t.Errorf("Expected running 1, got %d", stats.Running)
		}
	})

	// === Test SendTask ===
	t.Run("SendTask", func(t *testing.T) {
		// Give bash time to start
		time.Sleep(100 * time.Millisecond)

		err := coord.SendTask("integ-test", "echo 'hello from gforge'")
		if err != nil {
			t.Fatalf("SendTask failed: %v", err)
		}
	})

	// === Test Stop ===
	t.Run("Stop", func(t *testing.T) {
		err := coord.Stop("integ-test")
		if err != nil {
			t.Fatalf("Stop failed: %v", err)
		}

		goblin, _ := coord.Get("integ-test")
		if goblin.Status != "stopped" {
			t.Errorf("Expected status 'stopped', got '%s'", goblin.Status)
		}
	})

	// === Test Kill ===
	t.Run("Kill", func(t *testing.T) {
		err := coord.Kill("integ-test")
		if err != nil {
			t.Fatalf("Kill failed: %v", err)
		}

		goblin, _ := coord.Get("integ-test")
		if goblin != nil {
			t.Error("Goblin should be deleted")
		}
	})
}

// TestTmuxWorkspaceIntegration tests tmux and workspace working together
func TestTmuxWorkspaceIntegration(t *testing.T) {
	skipIfNoGit(t)
	skipIfNoTmux(t)

	tmpDir, err := os.MkdirTemp("", "gforge-tmux-ws-*")
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
	os.WriteFile(filepath.Join(repoDir, "test.txt"), []byte("initial\n"), 0644)
	exec.Command("git", "-C", repoDir, "add", ".").Run()
	exec.Command("git", "-C", repoDir, "commit", "-m", "Initial").Run()

	// Setup components
	wtDir := filepath.Join(tmpDir, "worktrees")
	wsMgr := workspace.NewWorktreeManager(workspace.Config{BasePath: wtDir})

	tmuxMgr := tmux.NewManager(tmux.Config{
		SocketName: "gforge-tmux-ws-test",
		CaptureDir: filepath.Join(tmpDir, "captures"),
	})
	defer exec.Command("tmux", "-L", "gforge-tmux-ws-test", "kill-server").Run()

	// Create worktree
	wt, err := wsMgr.Create(repoDir, "test-wt", "gforge/test")
	if err != nil {
		t.Fatalf("Failed to create worktree: %v", err)
	}

	// Create tmux session in worktree
	session, err := tmuxMgr.Create("test-session", wt.Path)
	if err != nil {
		t.Fatalf("Failed to create session: %v", err)
	}
	defer tmuxMgr.Kill("test-session")

	// Verify session
	if session.WorkDir != wt.Path {
		t.Errorf("Session workdir mismatch: expected '%s', got '%s'", wt.Path, session.WorkDir)
	}

	// Send command to create a file
	err = tmuxMgr.SendCommand("test-session", "echo 'new content' > new-file.txt")
	if err != nil {
		t.Fatalf("Failed to send command: %v", err)
	}

	// Wait for command to execute
	time.Sleep(200 * time.Millisecond)

	// Check for changes in worktree
	changes, err := wsMgr.GetChanges(wt.Path)
	if err != nil {
		t.Fatalf("Failed to get changes: %v", err)
	}

	if len(changes) != 1 {
		t.Errorf("Expected 1 change, got %d", len(changes))
	}

	// Commit the change
	hash, err := wsMgr.Commit(wt.Path, "Add new file")
	if err != nil {
		t.Fatalf("Failed to commit: %v", err)
	}

	if hash == "" {
		t.Error("Commit hash should not be empty")
	}

	// Verify no changes after commit
	changes, _ = wsMgr.GetChanges(wt.Path)
	if len(changes) != 0 {
		t.Errorf("Expected 0 changes after commit, got %d", len(changes))
	}

	// Cleanup worktree
	err = wsMgr.Remove(wt.Path, false)
	if err != nil {
		t.Errorf("Failed to remove worktree: %v", err)
	}
}

// TestAgentRegistryIntegration tests agent registry with coordinator
func TestAgentRegistryIntegration(t *testing.T) {
	registry := agents.NewRegistry()

	// Test that all built-in agents are present
	expectedAgents := []string{"claude", "claude-auto", "codex", "gemini", "ollama"}
	for _, name := range expectedAgents {
		agent := registry.Get(name)
		if agent == nil {
			t.Errorf("Expected agent '%s' to be registered", name)
			continue
		}

		// Verify agent has required fields
		if agent.Command == "" {
			t.Errorf("Agent '%s' should have a command", name)
		}

		if len(agent.Capabilities) == 0 {
			t.Errorf("Agent '%s' should have capabilities", name)
		}

		// Verify command generation works
		cmd := agent.GetCommand()
		if len(cmd) == 0 {
			t.Errorf("Agent '%s' should generate command", name)
		}
	}

	// Test scan doesn't error (even if no agents installed)
	detected := registry.Scan()
	_ = detected // May be empty in CI
}

// TestMultipleGoblins tests running multiple goblins simultaneously
func TestMultipleGoblins(t *testing.T) {
	skipIfNoGit(t)
	skipIfNoTmux(t)

	tmpDir, err := os.MkdirTemp("", "gforge-multi-*")
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

	// Setup coordinator
	dbPath := filepath.Join(tmpDir, "gforge.db")
	db, _ := storage.New(dbPath)
	defer db.Close()

	cfg := &config.Config{
		DatabasePath: dbPath,
		WorktreeBase: filepath.Join(tmpDir, "worktrees"),
		Tmux:         config.TmuxConfig{SocketName: "gforge-multi-test"},
	}
	os.MkdirAll(cfg.WorktreeBase, 0755)

	coord := coordinator.New(db, cfg, nil)
	defer exec.Command("tmux", "-L", "gforge-multi-test", "kill-server").Run()

	agent := &agents.Agent{
		Name:    "bash",
		Command: "bash",
		Args:    []string{},
	}

	// Spawn multiple goblins
	names := []string{"goblin-1", "goblin-2", "goblin-3"}
	for i, name := range names {
		_, err := coord.Spawn(coordinator.SpawnOptions{
			Name:        name,
			Agent:       agent,
			ProjectPath: repoDir,
			Branch:      filepath.Join("gforge", name),
		})
		if err != nil {
			t.Fatalf("Failed to spawn %s: %v", name, err)
		}
		defer coord.Kill(name)

		// Verify count increases
		goblins, _ := coord.List()
		if len(goblins) != i+1 {
			t.Errorf("Expected %d goblins, got %d", i+1, len(goblins))
		}
	}

	// Verify stats
	stats, _ := coord.Stats()
	if stats.Running != 3 {
		t.Errorf("Expected 3 running, got %d", stats.Running)
	}

	// Kill one
	coord.Kill("goblin-2")

	goblins, _ := coord.List()
	if len(goblins) != 2 {
		t.Errorf("Expected 2 goblins after kill, got %d", len(goblins))
	}
}
