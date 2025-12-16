package integrations

import (
	"testing"
)

func TestParseIssueRef(t *testing.T) {
	tests := []struct {
		input       string
		wantOwner   string
		wantRepo    string
		wantNumber  int
		shouldError bool
	}{
		{"owner/repo#123", "owner", "repo", 123, false},
		{"#456", "", "", 456, false},
		{"789", "", "", 789, false},
		{"invalid", "", "", 0, true},
		{"owner/repo", "", "", 0, true},
	}

	for _, tc := range tests {
		owner, repo, number, err := parseIssueRef(tc.input)
		if tc.shouldError {
			if err == nil {
				t.Errorf("parseIssueRef(%q) should error", tc.input)
			}
			continue
		}

		if err != nil {
			t.Errorf("parseIssueRef(%q) unexpected error: %v", tc.input, err)
			continue
		}

		if owner != tc.wantOwner {
			t.Errorf("parseIssueRef(%q) owner = %q, want %q", tc.input, owner, tc.wantOwner)
		}
		if repo != tc.wantRepo {
			t.Errorf("parseIssueRef(%q) repo = %q, want %q", tc.input, repo, tc.wantRepo)
		}
		if number != tc.wantNumber {
			t.Errorf("parseIssueRef(%q) number = %d, want %d", tc.input, number, tc.wantNumber)
		}
	}
}

func TestGeneratePRBody(t *testing.T) {
	commits := []string{
		"Fix login bug",
		"Add unit tests",
	}

	issue := &Issue{
		Number: 42,
		Title:  "Login broken",
		Body:   "Users can't login",
	}

	body := GeneratePRBody(commits, issue)

	if body == "" {
		t.Error("Generated body should not be empty")
	}

	if !contains(body, "Resolves #42") {
		t.Error("Body should contain issue reference")
	}

	if !contains(body, "Fix login bug") {
		t.Error("Body should contain commit message")
	}
}

func TestGeneratePRBodyNoIssue(t *testing.T) {
	commits := []string{"Some change"}
	body := GeneratePRBody(commits, nil)

	if body == "" {
		t.Error("Generated body should not be empty")
	}

	if contains(body, "Resolves #") {
		t.Error("Body should not contain issue reference")
	}
}

func TestNewGitHubClient(t *testing.T) {
	client := NewGitHubClient()
	if client == nil {
		t.Error("Client should not be nil")
	}
}

func TestNewLinearClient(t *testing.T) {
	client := NewLinearClient()
	if client == nil {
		t.Error("Client should not be nil")
	}

	// Should not be configured without env var
	if client.IsConfigured() {
		t.Log("Linear client is configured (env var set)")
	}
}

func TestNewJiraClient(t *testing.T) {
	client := NewJiraClient()
	if client == nil {
		t.Error("Client should not be nil")
	}

	// Should not be configured without env vars
	if client.IsConfigured() {
		t.Log("Jira client is configured (env vars set)")
	}
}

func TestParseJiraRef(t *testing.T) {
	tests := []struct {
		input       string
		want        string
		shouldError bool
	}{
		{"PROJ-123", "PROJ-123", false},
		{"ABC-1", "ABC-1", false},
		{"https://company.atlassian.net/browse/PROJ-456", "PROJ-456", false},
		{"invalid", "", true},
		{"proj-123", "", true}, // Lowercase not valid
	}

	for _, tc := range tests {
		result, err := ParseJiraRef(tc.input)
		if tc.shouldError {
			if err == nil {
				t.Errorf("ParseJiraRef(%q) should error", tc.input)
			}
			continue
		}

		if err != nil {
			t.Errorf("ParseJiraRef(%q) unexpected error: %v", tc.input, err)
			continue
		}

		if result != tc.want {
			t.Errorf("ParseJiraRef(%q) = %q, want %q", tc.input, result, tc.want)
		}
	}
}

func TestGetDefaultEditor(t *testing.T) {
	editor := GetDefaultEditor()
	if editor.Command == "" {
		t.Error("Default editor should have a command")
	}
}

func TestGetEditor(t *testing.T) {
	tests := []struct {
		name    string
		wantCmd string
	}{
		{"vscode", "code"},
		{"code", "code"},
		{"vim", "vim"},
		{"nvim", "nvim"},
	}

	for _, tc := range tests {
		editor, err := GetEditor(tc.name)
		if err != nil {
			continue // Editor may not be installed
		}
		if editor.Command != tc.wantCmd {
			t.Errorf("GetEditor(%q).Command = %q, want %q", tc.name, editor.Command, tc.wantCmd)
		}
	}
}

func TestEditorIsTerminal(t *testing.T) {
	if !EditorVim.isTerminal() {
		t.Error("vim should be terminal editor")
	}
	if !EditorNvim.isTerminal() {
		t.Error("nvim should be terminal editor")
	}
	if EditorVSCode.isTerminal() {
		t.Error("vscode should not be terminal editor")
	}
}

func TestListAvailableEditors(t *testing.T) {
	editors := ListAvailableEditors()
	// Should return at least empty list, not nil
	if editors == nil {
		t.Error("Should return list, not nil")
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsHelper(s, substr))
}

func containsHelper(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
