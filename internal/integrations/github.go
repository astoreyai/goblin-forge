package integrations

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"regexp"
	"strings"
)

// GitHubClient handles GitHub integration via gh CLI
type GitHubClient struct {
	// Uses gh CLI under the hood for authentication
}

// Issue represents a GitHub issue
type Issue struct {
	Number      int      `json:"number"`
	Title       string   `json:"title"`
	Body        string   `json:"body"`
	State       string   `json:"state"`
	URL         string   `json:"url"`
	Labels      []string `json:"labels"`
	Assignees   []string `json:"assignees"`
	CreatedAt   string   `json:"createdAt"`
	UpdatedAt   string   `json:"updatedAt"`
	Repository  string   `json:"repository"`
}

// PullRequest represents a GitHub pull request
type PullRequest struct {
	Number    int    `json:"number"`
	Title     string `json:"title"`
	Body      string `json:"body"`
	State     string `json:"state"`
	URL       string `json:"url"`
	HeadRef   string `json:"headRefName"`
	BaseRef   string `json:"baseRefName"`
	Draft     bool   `json:"isDraft"`
	Mergeable string `json:"mergeable"`
}

// PROptions contains options for creating a PR
type PROptions struct {
	Title    string
	Body     string
	Draft    bool
	Base     string // Target branch (default: main)
	Labels   []string
	Assignee string
}

// NewGitHubClient creates a new GitHub client
func NewGitHubClient() *GitHubClient {
	return &GitHubClient{}
}

// IsAuthenticated checks if gh CLI is authenticated
func (g *GitHubClient) IsAuthenticated() bool {
	cmd := exec.Command("gh", "auth", "status")
	return cmd.Run() == nil
}

// GetIssue fetches an issue by reference (e.g., "owner/repo#123")
func (g *GitHubClient) GetIssue(ref string) (*Issue, error) {
	owner, repo, number, err := parseIssueRef(ref)
	if err != nil {
		return nil, err
	}

	args := []string{"issue", "view", fmt.Sprintf("%d", number),
		"--json", "number,title,body,state,url,labels,assignees,createdAt,updatedAt"}

	if owner != "" && repo != "" {
		args = append(args, "--repo", fmt.Sprintf("%s/%s", owner, repo))
	}

	output, err := g.runGH(args...)
	if err != nil {
		return nil, fmt.Errorf("failed to get issue: %w", err)
	}

	var issue struct {
		Number    int    `json:"number"`
		Title     string `json:"title"`
		Body      string `json:"body"`
		State     string `json:"state"`
		URL       string `json:"url"`
		CreatedAt string `json:"createdAt"`
		UpdatedAt string `json:"updatedAt"`
		Labels    []struct {
			Name string `json:"name"`
		} `json:"labels"`
		Assignees []struct {
			Login string `json:"login"`
		} `json:"assignees"`
	}

	if err := json.Unmarshal(output, &issue); err != nil {
		return nil, fmt.Errorf("failed to parse issue: %w", err)
	}

	result := &Issue{
		Number:    issue.Number,
		Title:     issue.Title,
		Body:      issue.Body,
		State:     issue.State,
		URL:       issue.URL,
		CreatedAt: issue.CreatedAt,
		UpdatedAt: issue.UpdatedAt,
	}

	for _, l := range issue.Labels {
		result.Labels = append(result.Labels, l.Name)
	}
	for _, a := range issue.Assignees {
		result.Assignees = append(result.Assignees, a.Login)
	}

	return result, nil
}

// ListIssues lists issues for the current repository
func (g *GitHubClient) ListIssues(state string, limit int) ([]*Issue, error) {
	args := []string{"issue", "list", "--json", "number,title,state,url,labels"}

	if state != "" {
		args = append(args, "--state", state)
	}
	if limit > 0 {
		args = append(args, "--limit", fmt.Sprintf("%d", limit))
	}

	output, err := g.runGH(args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list issues: %w", err)
	}

	var issues []struct {
		Number int    `json:"number"`
		Title  string `json:"title"`
		State  string `json:"state"`
		URL    string `json:"url"`
		Labels []struct {
			Name string `json:"name"`
		} `json:"labels"`
	}

	if err := json.Unmarshal(output, &issues); err != nil {
		return nil, fmt.Errorf("failed to parse issues: %w", err)
	}

	result := make([]*Issue, len(issues))
	for i, issue := range issues {
		result[i] = &Issue{
			Number: issue.Number,
			Title:  issue.Title,
			State:  issue.State,
			URL:    issue.URL,
		}
		for _, l := range issue.Labels {
			result[i].Labels = append(result[i].Labels, l.Name)
		}
	}

	return result, nil
}

// CreatePR creates a new pull request
func (g *GitHubClient) CreatePR(branch string, opts PROptions) (*PullRequest, error) {
	args := []string{"pr", "create", "--head", branch}

	if opts.Title != "" {
		args = append(args, "--title", opts.Title)
	}
	if opts.Body != "" {
		args = append(args, "--body", opts.Body)
	}
	if opts.Draft {
		args = append(args, "--draft")
	}
	if opts.Base != "" {
		args = append(args, "--base", opts.Base)
	}
	for _, label := range opts.Labels {
		args = append(args, "--label", label)
	}
	if opts.Assignee != "" {
		args = append(args, "--assignee", opts.Assignee)
	}

	output, err := g.runGH(args...)
	if err != nil {
		return nil, fmt.Errorf("failed to create PR: %w", err)
	}

	// gh pr create returns the URL
	url := strings.TrimSpace(string(output))

	// Get PR details
	return g.GetPRByURL(url)
}

// GetPR gets a PR by number
func (g *GitHubClient) GetPR(number int) (*PullRequest, error) {
	args := []string{"pr", "view", fmt.Sprintf("%d", number),
		"--json", "number,title,body,state,url,headRefName,baseRefName,isDraft,mergeable"}

	output, err := g.runGH(args...)
	if err != nil {
		return nil, fmt.Errorf("failed to get PR: %w", err)
	}

	var pr PullRequest
	if err := json.Unmarshal(output, &pr); err != nil {
		return nil, fmt.Errorf("failed to parse PR: %w", err)
	}

	return &pr, nil
}

// GetPRByURL gets a PR by its URL
func (g *GitHubClient) GetPRByURL(url string) (*PullRequest, error) {
	// Extract number from URL
	re := regexp.MustCompile(`/pull/(\d+)`)
	matches := re.FindStringSubmatch(url)
	if len(matches) < 2 {
		return nil, fmt.Errorf("invalid PR URL: %s", url)
	}

	var number int
	fmt.Sscanf(matches[1], "%d", &number)

	return g.GetPR(number)
}

// MergePR merges a PR
func (g *GitHubClient) MergePR(number int, method string) error {
	args := []string{"pr", "merge", fmt.Sprintf("%d", number)}

	switch method {
	case "squash":
		args = append(args, "--squash")
	case "rebase":
		args = append(args, "--rebase")
	default:
		args = append(args, "--merge")
	}

	args = append(args, "--delete-branch")

	_, err := g.runGH(args...)
	return err
}

// LinkIssueToPR links an issue to a PR
func (g *GitHubClient) LinkIssueToPR(issueNum, prNum int) error {
	// Add "Fixes #N" to PR body
	pr, err := g.GetPR(prNum)
	if err != nil {
		return err
	}

	linkText := fmt.Sprintf("Fixes #%d", issueNum)
	if !strings.Contains(pr.Body, linkText) {
		newBody := pr.Body + "\n\n" + linkText
		_, err := g.runGH("pr", "edit", fmt.Sprintf("%d", prNum), "--body", newBody)
		return err
	}

	return nil
}

func (g *GitHubClient) runGH(args ...string) ([]byte, error) {
	cmd := exec.Command("gh", args...)
	return cmd.Output()
}

// parseIssueRef parses "owner/repo#123" or "#123" or "123"
func parseIssueRef(ref string) (owner, repo string, number int, err error) {
	// Full format: owner/repo#123
	fullRe := regexp.MustCompile(`^([^/]+)/([^#]+)#(\d+)$`)
	if matches := fullRe.FindStringSubmatch(ref); len(matches) == 4 {
		fmt.Sscanf(matches[3], "%d", &number)
		return matches[1], matches[2], number, nil
	}

	// Short format: #123 or 123
	shortRe := regexp.MustCompile(`^#?(\d+)$`)
	if matches := shortRe.FindStringSubmatch(ref); len(matches) == 2 {
		fmt.Sscanf(matches[1], "%d", &number)
		return "", "", number, nil
	}

	return "", "", 0, fmt.Errorf("invalid issue reference: %s (use owner/repo#123 or #123)")
}

// GeneratePRBody generates a PR body from commits
func GeneratePRBody(commits []string, issue *Issue) string {
	var body strings.Builder

	body.WriteString("## Summary\n\n")

	if issue != nil {
		body.WriteString(fmt.Sprintf("Resolves #%d\n\n", issue.Number))
		body.WriteString("### Issue Description\n\n")
		// Truncate long issue bodies
		issueBody := issue.Body
		if len(issueBody) > 500 {
			issueBody = issueBody[:500] + "..."
		}
		body.WriteString(issueBody)
		body.WriteString("\n\n")
	}

	body.WriteString("### Changes\n\n")
	for _, commit := range commits {
		body.WriteString(fmt.Sprintf("- %s\n", commit))
	}

	body.WriteString("\n## Test Plan\n\n")
	body.WriteString("- [ ] Unit tests added/updated\n")
	body.WriteString("- [ ] Manual testing completed\n")
	body.WriteString("- [ ] Documentation updated\n")

	return body.String()
}
