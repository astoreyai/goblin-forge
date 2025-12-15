package main

import (
	"fmt"
	"os"
	"path/filepath"
	"text/tabwriter"

	"github.com/astoreyai/goblin-forge/internal/agents"
	"github.com/astoreyai/goblin-forge/internal/coordinator"
)

// listAgents displays all available agent definitions
func listAgents() error {
	registry := agents.NewRegistry()

	fmt.Println("Available Agents:")
	fmt.Println()

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "NAME\tCOMMAND\tDESCRIPTION\tCAPABILITIES")
	fmt.Fprintln(w, "----\t-------\t-----------\t------------")

	for _, agent := range registry.List() {
		caps := ""
		for i, c := range agent.Capabilities {
			if i > 0 {
				caps += ", "
			}
			caps += c
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n",
			agent.Name, agent.Command, agent.Description, caps)
	}

	w.Flush()
	return nil
}

// scanAgents scans the system for installed agents
func scanAgents() error {
	registry := agents.NewRegistry()
	detected := registry.Scan()

	fmt.Println("Scanning for installed agents...")
	fmt.Println()

	if len(detected) == 0 {
		fmt.Println("No agents detected.")
		fmt.Println()
		fmt.Println("Install one of the supported agents:")
		fmt.Println("  - Claude Code: https://claude.ai/code")
		fmt.Println("  - Codex CLI:   npm install -g @openai/codex")
		fmt.Println("  - Gemini CLI:  pip install google-generativeai")
		fmt.Println("  - Ollama:      https://ollama.ai")
		return nil
	}

	fmt.Printf("Found %d agent(s):\n\n", len(detected))

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "AGENT\tVERSION\tPATH")
	fmt.Fprintln(w, "-----\t-------\t----")

	for _, d := range detected {
		fmt.Fprintf(w, "%s\t%s\t%s\n", d.Name, d.Version, d.Path)
	}

	w.Flush()

	// Show not found
	notFound := registry.NotInstalled(detected)
	if len(notFound) > 0 {
		fmt.Println()
		fmt.Println("Not installed:")
		for _, name := range notFound {
			agent := registry.Get(name)
			if agent != nil {
				fmt.Printf("  - %s: %s\n", name, agent.InstallHint)
			}
		}
	}

	return nil
}

// spawnGoblin creates a new goblin instance
func spawnGoblin(name, agentName, projectPath, branch string) error {
	registry := agents.NewRegistry()

	// Validate agent
	agent := registry.Get(agentName)
	if agent == nil {
		return fmt.Errorf("unknown agent: %s (available: claude, codex, gemini, ollama)", agentName)
	}

	// Resolve project path
	absPath, err := filepath.Abs(projectPath)
	if err != nil {
		return fmt.Errorf("invalid project path: %w", err)
	}

	// Check if project exists
	if _, err := os.Stat(absPath); os.IsNotExist(err) {
		return fmt.Errorf("project path does not exist: %s", absPath)
	}

	// Generate branch name if not provided
	if branch == "" {
		branch = fmt.Sprintf("gforge/%s", name)
	}

	// Create coordinator
	coord := coordinator.New(db, cfg, log)

	// Spawn goblin
	goblin, err := coord.Spawn(coordinator.SpawnOptions{
		Name:        name,
		Agent:       agent,
		ProjectPath: absPath,
		Branch:      branch,
	})
	if err != nil {
		return fmt.Errorf("failed to spawn goblin: %w", err)
	}

	fmt.Printf("Spawned goblin: %s\n", goblin.Name)
	fmt.Printf("  ID:       %s\n", goblin.ID)
	fmt.Printf("  Agent:    %s\n", goblin.Agent)
	fmt.Printf("  Branch:   %s\n", goblin.Branch)
	fmt.Printf("  Worktree: %s\n", goblin.WorktreePath)
	fmt.Printf("  Status:   %s\n", goblin.Status)
	fmt.Println()
	fmt.Printf("Attach with: gforge attach %s\n", name)

	return nil
}

// listGoblins displays all active goblins
func listGoblins() error {
	coord := coordinator.New(db, cfg, log)
	goblins, err := coord.List()
	if err != nil {
		return fmt.Errorf("failed to list goblins: %w", err)
	}

	if len(goblins) == 0 {
		fmt.Println("No active goblins.")
		fmt.Println()
		fmt.Println("Spawn one with: gforge spawn <name> --agent <agent>")
		return nil
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tNAME\tAGENT\tSTATUS\tBRANCH\tAGE")
	fmt.Fprintln(w, "--\t----\t-----\t------\t------\t---")

	for i, g := range goblins {
		fmt.Fprintf(w, "%d\t%s\t%s\t%s\t%s\t%s\n",
			i+1, g.Name, g.Agent, g.Status, g.Branch, g.Age())
	}

	w.Flush()
	return nil
}

// stopGoblin stops a running goblin
func stopGoblin(name string) error {
	coord := coordinator.New(db, cfg, log)

	if err := coord.Stop(name); err != nil {
		return fmt.Errorf("failed to stop goblin: %w", err)
	}

	fmt.Printf("Stopped goblin: %s\n", name)
	return nil
}

// showStatus displays system status
func showStatus() error {
	coord := coordinator.New(db, cfg, log)

	// Get stats
	stats, err := coord.Stats()
	if err != nil {
		return fmt.Errorf("failed to get stats: %w", err)
	}

	fmt.Println("Goblin Forge Status")
	fmt.Println("===================")
	fmt.Println()
	fmt.Printf("Goblins:\n")
	fmt.Printf("  Running:   %d\n", stats.Running)
	fmt.Printf("  Paused:    %d\n", stats.Paused)
	fmt.Printf("  Completed: %d\n", stats.Completed)
	fmt.Printf("  Total:     %d\n", stats.Total)
	fmt.Println()
	fmt.Printf("System:\n")
	fmt.Printf("  Config:    %s\n", config.GetConfigPath(cfgFile))
	fmt.Printf("  Database:  %s\n", cfg.DatabasePath)
	fmt.Printf("  Worktrees: %s\n", cfg.WorktreeBase)

	// Check for installed agents
	registry := agents.NewRegistry()
	detected := registry.Scan()
	fmt.Println()
	fmt.Printf("Agents: %d installed\n", len(detected))
	for _, d := range detected {
		fmt.Printf("  - %s (%s)\n", d.Name, d.Version)
	}

	return nil
}
