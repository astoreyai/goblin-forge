package integrations

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

// Editor represents an editor configuration
type Editor struct {
	Name    string
	Command string
	Args    []string
}

// Common editors
var (
	EditorVSCode = Editor{
		Name:    "vscode",
		Command: "code",
		Args:    []string{"-n"},
	}
	EditorCursor = Editor{
		Name:    "cursor",
		Command: "cursor",
		Args:    []string{"-n"},
	}
	EditorVim = Editor{
		Name:    "vim",
		Command: "vim",
		Args:    []string{},
	}
	EditorNvim = Editor{
		Name:    "nvim",
		Command: "nvim",
		Args:    []string{},
	}
	EditorEmacs = Editor{
		Name:    "emacs",
		Command: "emacs",
		Args:    []string{},
	}
	EditorSublime = Editor{
		Name:    "sublime",
		Command: "subl",
		Args:    []string{"-n"},
	}
	EditorZed = Editor{
		Name:    "zed",
		Command: "zed",
		Args:    []string{},
	}
)

// GetDefaultEditor returns the default editor based on $EDITOR or system preference
func GetDefaultEditor() Editor {
	// Check $EDITOR environment variable
	editorEnv := os.Getenv("EDITOR")
	if editorEnv != "" {
		return Editor{
			Name:    filepath.Base(editorEnv),
			Command: editorEnv,
			Args:    []string{},
		}
	}

	// Check $VISUAL environment variable
	visualEnv := os.Getenv("VISUAL")
	if visualEnv != "" {
		return Editor{
			Name:    filepath.Base(visualEnv),
			Command: visualEnv,
			Args:    []string{},
		}
	}

	// Platform defaults
	switch runtime.GOOS {
	case "darwin":
		// macOS: prefer VS Code if available
		if isExecutable("code") {
			return EditorVSCode
		}
	case "linux":
		// Linux: check common editors
		if isExecutable("code") {
			return EditorVSCode
		}
		if isExecutable("nvim") {
			return EditorNvim
		}
		if isExecutable("vim") {
			return EditorVim
		}
	}

	// Fallback to vim
	return EditorVim
}

// GetEditor returns an editor by name
func GetEditor(name string) (Editor, error) {
	name = strings.ToLower(name)

	switch name {
	case "code", "vscode":
		return EditorVSCode, nil
	case "cursor":
		return EditorCursor, nil
	case "vim", "vi":
		return EditorVim, nil
	case "nvim", "neovim":
		return EditorNvim, nil
	case "emacs":
		return EditorEmacs, nil
	case "subl", "sublime":
		return EditorSublime, nil
	case "zed":
		return EditorZed, nil
	default:
		// Try to use it as a command
		if isExecutable(name) {
			return Editor{
				Name:    name,
				Command: name,
				Args:    []string{},
			}, nil
		}
		return Editor{}, fmt.Errorf("unknown editor: %s", name)
	}
}

// Open opens a directory in the editor
func (e Editor) Open(path string) error {
	if !isExecutable(e.Command) {
		return fmt.Errorf("editor not found: %s", e.Command)
	}

	args := append(e.Args, path)
	cmd := exec.Command(e.Command, args...)

	// For terminal editors, we need to attach to the terminal
	if e.isTerminal() {
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}

	// For GUI editors, start in background
	return cmd.Start()
}

// OpenFile opens a specific file in the editor
func (e Editor) OpenFile(path string, line int) error {
	if !isExecutable(e.Command) {
		return fmt.Errorf("editor not found: %s", e.Command)
	}

	args := append([]string{}, e.Args...)

	// Add line number argument based on editor
	switch e.Name {
	case "vscode", "code", "cursor":
		args = append(args, "--goto", fmt.Sprintf("%s:%d", path, line))
	case "vim", "nvim":
		args = append(args, fmt.Sprintf("+%d", line), path)
	case "emacs":
		args = append(args, fmt.Sprintf("+%d", line), path)
	case "subl", "sublime":
		args = append(args, fmt.Sprintf("%s:%d", path, line))
	default:
		args = append(args, path)
	}

	cmd := exec.Command(e.Command, args...)

	if e.isTerminal() {
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}

	return cmd.Start()
}

// isTerminal returns true if the editor runs in terminal
func (e Editor) isTerminal() bool {
	terminalEditors := map[string]bool{
		"vim":   true,
		"nvim":  true,
		"vi":    true,
		"nano":  true,
		"emacs": true, // Can be GUI but often terminal
	}
	return terminalEditors[e.Name]
}

// isExecutable checks if a command is executable
func isExecutable(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

// ListAvailableEditors returns a list of available editors on the system
func ListAvailableEditors() []Editor {
	editors := []Editor{
		EditorVSCode,
		EditorCursor,
		EditorVim,
		EditorNvim,
		EditorEmacs,
		EditorSublime,
		EditorZed,
	}

	available := make([]Editor, 0)
	for _, e := range editors {
		if isExecutable(e.Command) {
			available = append(available, e)
		}
	}

	return available
}
