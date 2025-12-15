package storage

import (
	"database/sql"
	"fmt"
	"time"

	_ "modernc.org/sqlite"
)

// DB wraps the SQLite database connection
type DB struct {
	conn *sql.DB
	path string
}

// New creates a new database connection and runs migrations
func New(path string) (*DB, error) {
	conn, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Enable foreign keys and WAL mode
	pragmas := []string{
		"PRAGMA foreign_keys = ON",
		"PRAGMA journal_mode = WAL",
		"PRAGMA synchronous = NORMAL",
		"PRAGMA busy_timeout = 5000",
	}

	for _, pragma := range pragmas {
		if _, err := conn.Exec(pragma); err != nil {
			return nil, fmt.Errorf("failed to set pragma: %w", err)
		}
	}

	db := &DB{conn: conn, path: path}

	// Run migrations
	if err := db.migrate(); err != nil {
		return nil, fmt.Errorf("failed to run migrations: %w", err)
	}

	return db, nil
}

// Close closes the database connection
func (db *DB) Close() error {
	return db.conn.Close()
}

// migrate runs database migrations
func (db *DB) migrate() error {
	migrations := []string{
		// Goblins table
		`CREATE TABLE IF NOT EXISTS goblins (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL UNIQUE,
			agent TEXT NOT NULL,
			status TEXT NOT NULL DEFAULT 'created',
			project_path TEXT NOT NULL,
			worktree_path TEXT,
			branch TEXT,
			tmux_session TEXT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)`,

		// Sessions table (for voice commands, task history)
		`CREATE TABLE IF NOT EXISTS sessions (
			id TEXT PRIMARY KEY,
			goblin_id TEXT NOT NULL,
			task TEXT,
			started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			ended_at DATETIME,
			status TEXT NOT NULL DEFAULT 'active',
			FOREIGN KEY (goblin_id) REFERENCES goblins(id) ON DELETE CASCADE
		)`,

		// Voice commands history
		`CREATE TABLE IF NOT EXISTS voice_commands (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			raw_text TEXT NOT NULL,
			parsed_action TEXT,
			parsed_params TEXT,
			executed BOOLEAN DEFAULT FALSE,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)`,

		// Agent output logs
		`CREATE TABLE IF NOT EXISTS output_logs (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			goblin_id TEXT NOT NULL,
			content TEXT NOT NULL,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (goblin_id) REFERENCES goblins(id) ON DELETE CASCADE
		)`,

		// Projects table
		`CREATE TABLE IF NOT EXISTS projects (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			path TEXT NOT NULL UNIQUE,
			detected_type TEXT,
			last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP
		)`,

		// Indexes
		`CREATE INDEX IF NOT EXISTS idx_goblins_status ON goblins(status)`,
		`CREATE INDEX IF NOT EXISTS idx_goblins_name ON goblins(name)`,
		`CREATE INDEX IF NOT EXISTS idx_output_logs_goblin ON output_logs(goblin_id)`,
		`CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(path)`,
	}

	for _, m := range migrations {
		if _, err := db.conn.Exec(m); err != nil {
			return fmt.Errorf("migration failed: %w\nSQL: %s", err, m)
		}
	}

	return nil
}

// Goblin represents a goblin in the database
type Goblin struct {
	ID           string
	Name         string
	Agent        string
	Status       string
	ProjectPath  string
	WorktreePath string
	Branch       string
	TmuxSession  string
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// Age returns a human-readable age string
func (g *Goblin) Age() string {
	duration := time.Since(g.CreatedAt)

	if duration < time.Minute {
		return fmt.Sprintf("%ds", int(duration.Seconds()))
	} else if duration < time.Hour {
		return fmt.Sprintf("%dm", int(duration.Minutes()))
	} else if duration < 24*time.Hour {
		return fmt.Sprintf("%dh %dm", int(duration.Hours()), int(duration.Minutes())%60)
	}
	return fmt.Sprintf("%dd", int(duration.Hours()/24))
}

// CreateGoblin inserts a new goblin
func (db *DB) CreateGoblin(g *Goblin) error {
	query := `
		INSERT INTO goblins (id, name, agent, status, project_path, worktree_path, branch, tmux_session)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`
	_, err := db.conn.Exec(query,
		g.ID, g.Name, g.Agent, g.Status, g.ProjectPath, g.WorktreePath, g.Branch, g.TmuxSession)
	if err != nil {
		return fmt.Errorf("failed to create goblin: %w", err)
	}
	return nil
}

// GetGoblin retrieves a goblin by ID or name
func (db *DB) GetGoblin(idOrName string) (*Goblin, error) {
	query := `
		SELECT id, name, agent, status, project_path, worktree_path, branch, tmux_session, created_at, updated_at
		FROM goblins
		WHERE id = ? OR name = ?
	`
	row := db.conn.QueryRow(query, idOrName, idOrName)

	var g Goblin
	err := row.Scan(&g.ID, &g.Name, &g.Agent, &g.Status, &g.ProjectPath,
		&g.WorktreePath, &g.Branch, &g.TmuxSession, &g.CreatedAt, &g.UpdatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get goblin: %w", err)
	}
	return &g, nil
}

// ListGoblins returns all goblins
func (db *DB) ListGoblins() ([]*Goblin, error) {
	query := `
		SELECT id, name, agent, status, project_path, worktree_path, branch, tmux_session, created_at, updated_at
		FROM goblins
		ORDER BY created_at DESC
	`
	rows, err := db.conn.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to list goblins: %w", err)
	}
	defer rows.Close()

	var goblins []*Goblin
	for rows.Next() {
		var g Goblin
		err := rows.Scan(&g.ID, &g.Name, &g.Agent, &g.Status, &g.ProjectPath,
			&g.WorktreePath, &g.Branch, &g.TmuxSession, &g.CreatedAt, &g.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan goblin: %w", err)
		}
		goblins = append(goblins, &g)
	}

	return goblins, nil
}

// ListGoblinsByStatus returns goblins with a specific status
func (db *DB) ListGoblinsByStatus(status string) ([]*Goblin, error) {
	query := `
		SELECT id, name, agent, status, project_path, worktree_path, branch, tmux_session, created_at, updated_at
		FROM goblins
		WHERE status = ?
		ORDER BY created_at DESC
	`
	rows, err := db.conn.Query(query, status)
	if err != nil {
		return nil, fmt.Errorf("failed to list goblins: %w", err)
	}
	defer rows.Close()

	var goblins []*Goblin
	for rows.Next() {
		var g Goblin
		err := rows.Scan(&g.ID, &g.Name, &g.Agent, &g.Status, &g.ProjectPath,
			&g.WorktreePath, &g.Branch, &g.TmuxSession, &g.CreatedAt, &g.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan goblin: %w", err)
		}
		goblins = append(goblins, &g)
	}

	return goblins, nil
}

// UpdateGoblinStatus updates a goblin's status
func (db *DB) UpdateGoblinStatus(id, status string) error {
	query := `UPDATE goblins SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? OR name = ?`
	result, err := db.conn.Exec(query, status, id, id)
	if err != nil {
		return fmt.Errorf("failed to update goblin status: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("goblin not found: %s", id)
	}

	return nil
}

// DeleteGoblin removes a goblin
func (db *DB) DeleteGoblin(id string) error {
	query := `DELETE FROM goblins WHERE id = ? OR name = ?`
	result, err := db.conn.Exec(query, id, id)
	if err != nil {
		return fmt.Errorf("failed to delete goblin: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("goblin not found: %s", id)
	}

	return nil
}

// Stats represents aggregate statistics
type Stats struct {
	Total     int
	Running   int
	Paused    int
	Completed int
}

// GetStats returns aggregate statistics
func (db *DB) GetStats() (*Stats, error) {
	stats := &Stats{}

	// Total count
	row := db.conn.QueryRow("SELECT COUNT(*) FROM goblins")
	if err := row.Scan(&stats.Total); err != nil {
		return nil, err
	}

	// Running count
	row = db.conn.QueryRow("SELECT COUNT(*) FROM goblins WHERE status = 'running'")
	if err := row.Scan(&stats.Running); err != nil {
		return nil, err
	}

	// Paused count
	row = db.conn.QueryRow("SELECT COUNT(*) FROM goblins WHERE status = 'paused'")
	if err := row.Scan(&stats.Paused); err != nil {
		return nil, err
	}

	// Completed count
	row = db.conn.QueryRow("SELECT COUNT(*) FROM goblins WHERE status = 'completed'")
	if err := row.Scan(&stats.Completed); err != nil {
		return nil, err
	}

	return stats, nil
}

// LogOutput stores agent output
func (db *DB) LogOutput(goblinID, content string) error {
	query := `INSERT INTO output_logs (goblin_id, content) VALUES (?, ?)`
	_, err := db.conn.Exec(query, goblinID, content)
	return err
}

// GetRecentOutput retrieves recent output for a goblin
func (db *DB) GetRecentOutput(goblinID string, limit int) ([]string, error) {
	query := `
		SELECT content FROM output_logs
		WHERE goblin_id = ?
		ORDER BY created_at DESC
		LIMIT ?
	`
	rows, err := db.conn.Query(query, goblinID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var output []string
	for rows.Next() {
		var content string
		if err := rows.Scan(&content); err != nil {
			return nil, err
		}
		output = append(output, content)
	}

	// Reverse to get chronological order
	for i, j := 0, len(output)-1; i < j; i, j = i+1, j-1 {
		output[i], output[j] = output[j], output[i]
	}

	return output, nil
}
