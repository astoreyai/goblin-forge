package storage

import (
	"os"
	"path/filepath"
	"testing"
)

func TestNew(t *testing.T) {
	// Create temp directory
	tmpDir, err := os.MkdirTemp("", "gforge-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "test.db")

	// Create database
	db, err := New(dbPath)
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Verify file exists
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		t.Error("Database file was not created")
	}
}

func TestGoblinCRUD(t *testing.T) {
	// Create temp database
	tmpDir, err := os.MkdirTemp("", "gforge-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	db, err := New(filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Test Create
	goblin := &Goblin{
		ID:           "test-123",
		Name:         "test-goblin",
		Agent:        "claude",
		Status:       "running",
		ProjectPath:  "/tmp/test",
		WorktreePath: "/tmp/test-worktree",
		Branch:       "gforge/test",
		TmuxSession:  "gforge-test-123",
	}

	err = db.CreateGoblin(goblin)
	if err != nil {
		t.Fatalf("Failed to create goblin: %v", err)
	}

	// Test Get by ID
	retrieved, err := db.GetGoblin("test-123")
	if err != nil {
		t.Fatalf("Failed to get goblin by ID: %v", err)
	}
	if retrieved == nil {
		t.Fatal("Goblin not found by ID")
	}
	if retrieved.Name != "test-goblin" {
		t.Errorf("Expected name 'test-goblin', got '%s'", retrieved.Name)
	}

	// Test Get by Name
	retrieved, err = db.GetGoblin("test-goblin")
	if err != nil {
		t.Fatalf("Failed to get goblin by name: %v", err)
	}
	if retrieved == nil {
		t.Fatal("Goblin not found by name")
	}

	// Test List
	goblins, err := db.ListGoblins()
	if err != nil {
		t.Fatalf("Failed to list goblins: %v", err)
	}
	if len(goblins) != 1 {
		t.Errorf("Expected 1 goblin, got %d", len(goblins))
	}

	// Test Update Status
	err = db.UpdateGoblinStatus("test-123", "paused")
	if err != nil {
		t.Fatalf("Failed to update status: %v", err)
	}

	retrieved, _ = db.GetGoblin("test-123")
	if retrieved.Status != "paused" {
		t.Errorf("Expected status 'paused', got '%s'", retrieved.Status)
	}

	// Test Delete
	err = db.DeleteGoblin("test-123")
	if err != nil {
		t.Fatalf("Failed to delete goblin: %v", err)
	}

	retrieved, _ = db.GetGoblin("test-123")
	if retrieved != nil {
		t.Error("Goblin should have been deleted")
	}
}

func TestListGoblinsByStatus(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "gforge-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	db, err := New(filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Create goblins with different statuses
	statuses := []string{"running", "running", "paused", "completed"}
	for i, status := range statuses {
		goblin := &Goblin{
			ID:          string(rune('a' + i)),
			Name:        "goblin-" + string(rune('a'+i)),
			Agent:       "claude",
			Status:      status,
			ProjectPath: "/tmp",
		}
		if err := db.CreateGoblin(goblin); err != nil {
			t.Fatalf("Failed to create goblin: %v", err)
		}
	}

	// Test filtering by status
	running, err := db.ListGoblinsByStatus("running")
	if err != nil {
		t.Fatalf("Failed to list by status: %v", err)
	}
	if len(running) != 2 {
		t.Errorf("Expected 2 running goblins, got %d", len(running))
	}

	paused, _ := db.ListGoblinsByStatus("paused")
	if len(paused) != 1 {
		t.Errorf("Expected 1 paused goblin, got %d", len(paused))
	}
}

func TestStats(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "gforge-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	db, err := New(filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Create goblins with different statuses
	statuses := []string{"running", "running", "paused", "completed", "completed"}
	for i, status := range statuses {
		goblin := &Goblin{
			ID:          string(rune('a' + i)),
			Name:        "goblin-" + string(rune('a'+i)),
			Agent:       "claude",
			Status:      status,
			ProjectPath: "/tmp",
		}
		db.CreateGoblin(goblin)
	}

	stats, err := db.GetStats()
	if err != nil {
		t.Fatalf("Failed to get stats: %v", err)
	}

	if stats.Total != 5 {
		t.Errorf("Expected total 5, got %d", stats.Total)
	}
	if stats.Running != 2 {
		t.Errorf("Expected running 2, got %d", stats.Running)
	}
	if stats.Paused != 1 {
		t.Errorf("Expected paused 1, got %d", stats.Paused)
	}
	if stats.Completed != 2 {
		t.Errorf("Expected completed 2, got %d", stats.Completed)
	}
}

func TestOutputLogs(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "gforge-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	db, err := New(filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Create a goblin first
	goblin := &Goblin{
		ID:          "test-123",
		Name:        "test-goblin",
		Agent:       "claude",
		Status:      "running",
		ProjectPath: "/tmp",
	}
	db.CreateGoblin(goblin)

	// Log some output
	outputs := []string{"Line 1", "Line 2", "Line 3"}
	for _, o := range outputs {
		if err := db.LogOutput("test-123", o); err != nil {
			t.Fatalf("Failed to log output: %v", err)
		}
	}

	// Retrieve output
	retrieved, err := db.GetRecentOutput("test-123", 10)
	if err != nil {
		t.Fatalf("Failed to get output: %v", err)
	}

	if len(retrieved) != 3 {
		t.Errorf("Expected 3 lines, got %d", len(retrieved))
	}

	// Should be in chronological order
	if retrieved[0] != "Line 1" {
		t.Errorf("Expected 'Line 1', got '%s'", retrieved[0])
	}
}

func TestGoblinAge(t *testing.T) {
	goblin := &Goblin{}

	// Test various ages - these are approximate tests
	// since we can't easily test exact durations
	if age := goblin.Age(); age == "" {
		t.Error("Age should not be empty")
	}
}

func TestDuplicateGoblinName(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "gforge-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	db, err := New(filepath.Join(tmpDir, "test.db"))
	if err != nil {
		t.Fatalf("Failed to create database: %v", err)
	}
	defer db.Close()

	// Create first goblin
	goblin1 := &Goblin{
		ID:          "id-1",
		Name:        "duplicate-name",
		Agent:       "claude",
		Status:      "running",
		ProjectPath: "/tmp",
	}
	if err := db.CreateGoblin(goblin1); err != nil {
		t.Fatalf("Failed to create first goblin: %v", err)
	}

	// Try to create second with same name
	goblin2 := &Goblin{
		ID:          "id-2",
		Name:        "duplicate-name",
		Agent:       "claude",
		Status:      "running",
		ProjectPath: "/tmp",
	}
	err = db.CreateGoblin(goblin2)
	if err == nil {
		t.Error("Expected error when creating goblin with duplicate name")
	}
}
