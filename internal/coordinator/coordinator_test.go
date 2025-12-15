package coordinator

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"github.com/astoreyai/goblin-forge/internal/agents"
	"github.com/astoreyai/goblin-forge/internal/config"
	"github.com/astoreyai/goblin-forge/internal/logging"
	"github.com/astoreyai/goblin-forge/internal/storage"
)

func TestNew(t *testing.T) {
	coord := New(nil, nil, nil)
	if coord == nil {
		t.Fatal("Coordinator should not be nil")
	}
}

func TestGoblinAge(t *testing.T) {
	tests := []struct {
		created  time.Time
		expected string
	}{
		{time.Now().Add(-30 * time.Second), "30s"},
		{time.Now().Add(-5 * time.Minute), "5m"},
		{time.Now().Add(-2 * time.Hour), "2h 0m"},
		{time.Now().Add(-26 * time.Hour), "1d"},
	}

	for _, tc := range tests {
		g := &Goblin{CreatedAt: tc.created}
		age := g.Age()
		if age != tc.expected {
			t.Errorf("Expected '%s', got '%s'", tc.expected, age)
		}
	}
}

// Helper to check if git is available
func gitAvailable() bool {
	_, err := exec.LookPath("git")
	return err == nil
}

// Helper to check if tmux is available
func tmuxAvailable() bool {
	_, err := exec.LookPath("tmux")
	return err == nil
}

// Helper to create a test git repo
func createTestRepo(t *testing.T) (string, func()) {
	tmpDir, err := os.MkdirTemp("", "gforge-coord-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	cleanup := func() {
		os.RemoveAll(tmpDir)
	}

	// Initialize git repo
	cmd := exec.Command("git", "init", tmpDir)
	if err := cmd.Run(); err != nil {
		cleanup()
		t.Fatalf("Failed to init git repo: %v", err)
	}

	// Configure git
	exec.Command("git", "-C", tmpDir, "config", "user.email", "test@test.com").Run()
	exec.Command("git", "-C", tmpDir, "config", "user.name", "Test").Run()

	// Create initial commit
	testFile := filepath.Join(tmpDir, "README.md")
	os.WriteFile(testFile, []byte("# Test\n"), 0644)
	exec.Command("git", "-C", tmpDir, "add", ".").Run()
	exec.Command("git", "-C", tmpDir, "commit", "-m", "Initial commit").Run()

	return tmpDir, cleanup
}

// Setup test coordinator with temp database
func setupCoordinator(t *testing.T) (*Coordinator, *config.Config, func()) {
	tmpDir, err := os.MkdirTemp("", "gforge-coord-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	dbPath := filepath.Join(tmpDir, "test.db")
	db, err := storage.New(dbPath)
	if err != nil {
		os.RemoveAll(tmpDir)
		t.Fatalf("Failed to create database: %v", err)
	}

	cfg := &config.Config{
		DatabasePath: dbPath,
		WorktreeBase: filepath.Join(tmpDir, "worktrees"),
		Tmux: config.TmuxConfig{
			SocketName: "gforge-test-coord",
		},
	}

	os.MkdirAll(cfg.WorktreeBase, 0755)

	log := logging.New(false)

	cleanup := func() {
		// Clean up tmux sessions
		exec.Command("tmux", "-L", "gforge-test-coord", "kill-server").Run()
		db.Close()
		os.RemoveAll(tmpDir)
	}

	return New(db, cfg, log), cfg, cleanup
}

func TestListEmpty(t *testing.T) {
	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	goblins, err := coord.List()
	if err != nil {
		t.Fatalf("List should not error: %v", err)
	}

	if len(goblins) != 0 {
		t.Errorf("Expected 0 goblins, got %d", len(goblins))
	}
}

func TestStatsEmpty(t *testing.T) {
	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	stats, err := coord.Stats()
	if err != nil {
		t.Fatalf("Stats should not error: %v", err)
	}

	if stats.Total != 0 {
		t.Errorf("Expected 0 total, got %d", stats.Total)
	}
}

func TestGetNonexistent(t *testing.T) {
	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	goblin, err := coord.Get("nonexistent")
	if err != nil {
		t.Fatalf("Get should not error: %v", err)
	}

	if goblin != nil {
		t.Error("Should return nil for nonexistent goblin")
	}
}

func TestSpawnDuplicateName(t *testing.T) {
	if !gitAvailable() || !tmuxAvailable() {
		t.Skip("git or tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	repoPath, repoCleanup := createTestRepo(t)
	defer repoCleanup()

	agent := &agents.Agent{
		Name:    "echo",
		Command: "echo",
		Args:    []string{"test"},
	}

	// First spawn should succeed
	_, err := coord.Spawn(SpawnOptions{
		Name:        "test-goblin",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/test-1",
	})
	if err != nil {
		t.Fatalf("First spawn should succeed: %v", err)
	}
	defer coord.Kill("test-goblin")

	// Second spawn with same name should fail
	_, err = coord.Spawn(SpawnOptions{
		Name:        "test-goblin",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/test-2",
	})
	if err == nil {
		t.Error("Should fail when spawning duplicate name")
	}
}

func TestSpawnAndList(t *testing.T) {
	if !gitAvailable() || !tmuxAvailable() {
		t.Skip("git or tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	repoPath, repoCleanup := createTestRepo(t)
	defer repoCleanup()

	agent := &agents.Agent{
		Name:    "echo",
		Command: "echo",
		Args:    []string{"hello"},
	}

	// Spawn
	goblin, err := coord.Spawn(SpawnOptions{
		Name:        "list-test",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/list-test",
	})
	if err != nil {
		t.Fatalf("Spawn failed: %v", err)
	}
	defer coord.Kill("list-test")

	if goblin.Name != "list-test" {
		t.Errorf("Expected name 'list-test', got '%s'", goblin.Name)
	}

	if goblin.Status != "running" {
		t.Errorf("Expected status 'running', got '%s'", goblin.Status)
	}

	// List
	goblins, err := coord.List()
	if err != nil {
		t.Fatalf("List failed: %v", err)
	}

	if len(goblins) != 1 {
		t.Errorf("Expected 1 goblin, got %d", len(goblins))
	}
}

func TestSpawnAndGet(t *testing.T) {
	if !gitAvailable() || !tmuxAvailable() {
		t.Skip("git or tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	repoPath, repoCleanup := createTestRepo(t)
	defer repoCleanup()

	agent := &agents.Agent{
		Name:    "echo",
		Command: "echo",
		Args:    []string{"hello"},
	}

	// Spawn
	created, err := coord.Spawn(SpawnOptions{
		Name:        "get-test",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/get-test",
	})
	if err != nil {
		t.Fatalf("Spawn failed: %v", err)
	}
	defer coord.Kill("get-test")

	// Get by name
	goblin, err := coord.Get("get-test")
	if err != nil {
		t.Fatalf("Get by name failed: %v", err)
	}

	if goblin.ID != created.ID {
		t.Error("ID mismatch")
	}

	// Get by ID
	goblin, err = coord.Get(created.ID)
	if err != nil {
		t.Fatalf("Get by ID failed: %v", err)
	}

	if goblin.Name != "get-test" {
		t.Errorf("Name mismatch")
	}
}

func TestStop(t *testing.T) {
	if !gitAvailable() || !tmuxAvailable() {
		t.Skip("git or tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	repoPath, repoCleanup := createTestRepo(t)
	defer repoCleanup()

	agent := &agents.Agent{
		Name:    "echo",
		Command: "echo",
		Args:    []string{"hello"},
	}

	// Spawn
	_, err := coord.Spawn(SpawnOptions{
		Name:        "stop-test",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/stop-test",
	})
	if err != nil {
		t.Fatalf("Spawn failed: %v", err)
	}
	defer coord.Kill("stop-test")

	// Stop
	err = coord.Stop("stop-test")
	if err != nil {
		t.Fatalf("Stop failed: %v", err)
	}

	// Check status
	goblin, _ := coord.Get("stop-test")
	if goblin.Status != "stopped" {
		t.Errorf("Expected status 'stopped', got '%s'", goblin.Status)
	}
}

func TestKill(t *testing.T) {
	if !gitAvailable() || !tmuxAvailable() {
		t.Skip("git or tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	repoPath, repoCleanup := createTestRepo(t)
	defer repoCleanup()

	agent := &agents.Agent{
		Name:    "echo",
		Command: "echo",
		Args:    []string{"hello"},
	}

	// Spawn
	_, err := coord.Spawn(SpawnOptions{
		Name:        "kill-test",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/kill-test",
	})
	if err != nil {
		t.Fatalf("Spawn failed: %v", err)
	}

	// Kill
	err = coord.Kill("kill-test")
	if err != nil {
		t.Fatalf("Kill failed: %v", err)
	}

	// Should be gone
	goblin, _ := coord.Get("kill-test")
	if goblin != nil {
		t.Error("Goblin should be deleted after kill")
	}
}

func TestStopNonexistent(t *testing.T) {
	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	err := coord.Stop("nonexistent")
	if err == nil {
		t.Error("Should error when stopping nonexistent goblin")
	}
}

func TestKillNonexistent(t *testing.T) {
	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	err := coord.Kill("nonexistent")
	if err == nil {
		t.Error("Should error when killing nonexistent goblin")
	}
}

func TestSendTask(t *testing.T) {
	if !gitAvailable() || !tmuxAvailable() {
		t.Skip("git or tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	repoPath, repoCleanup := createTestRepo(t)
	defer repoCleanup()

	agent := &agents.Agent{
		Name:    "cat",
		Command: "cat", // cat will wait for input
		Args:    []string{},
	}

	// Spawn
	_, err := coord.Spawn(SpawnOptions{
		Name:        "task-test",
		Agent:       agent,
		ProjectPath: repoPath,
		Branch:      "gforge/task-test",
	})
	if err != nil {
		t.Fatalf("Spawn failed: %v", err)
	}
	defer coord.Kill("task-test")

	// Give it time to start
	time.Sleep(100 * time.Millisecond)

	// Send task
	err = coord.SendTask("task-test", "hello world")
	if err != nil {
		t.Fatalf("SendTask failed: %v", err)
	}
}

func TestSendTaskNonexistent(t *testing.T) {
	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	err := coord.SendTask("nonexistent", "test task")
	if err == nil {
		t.Error("Should error when sending task to nonexistent goblin")
	}
}

func TestNonGitProject(t *testing.T) {
	if !tmuxAvailable() {
		t.Skip("tmux not available")
	}

	coord, _, cleanup := setupCoordinator(t)
	defer cleanup()

	// Create a non-git directory
	tmpDir, err := os.MkdirTemp("", "gforge-nongit-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	agent := &agents.Agent{
		Name:    "echo",
		Command: "echo",
		Args:    []string{"hello"},
	}

	// Spawn in non-git directory should work
	goblin, err := coord.Spawn(SpawnOptions{
		Name:        "nongit-test",
		Agent:       agent,
		ProjectPath: tmpDir,
		Branch:      "gforge/nongit",
	})
	if err != nil {
		t.Fatalf("Spawn in non-git dir failed: %v", err)
	}
	defer coord.Kill("nongit-test")

	// WorktreePath should be the original dir for non-git projects
	if goblin.WorktreePath != tmpDir {
		t.Errorf("Expected worktree path '%s', got '%s'", tmpDir, goblin.WorktreePath)
	}
}
