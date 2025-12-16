package integrations

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
)

const linearAPIURL = "https://api.linear.app/graphql"

// LinearClient handles Linear integration
type LinearClient struct {
	apiKey string
	client *http.Client
}

// LinearIssue represents a Linear issue
type LinearIssue struct {
	ID          string   `json:"id"`
	Identifier  string   `json:"identifier"` // e.g., "PROJ-123"
	Title       string   `json:"title"`
	Description string   `json:"description"`
	State       string   `json:"state"`
	Priority    int      `json:"priority"`
	URL         string   `json:"url"`
	Labels      []string `json:"labels"`
	Assignee    string   `json:"assignee"`
	CreatedAt   string   `json:"createdAt"`
	UpdatedAt   string   `json:"updatedAt"`
}

// NewLinearClient creates a new Linear client
func NewLinearClient() *LinearClient {
	return &LinearClient{
		apiKey: os.Getenv("LINEAR_API_KEY"),
		client: &http.Client{},
	}
}

// IsConfigured checks if Linear is configured
func (l *LinearClient) IsConfigured() bool {
	return l.apiKey != ""
}

// GetIssue fetches a Linear issue by identifier (e.g., "PROJ-123")
func (l *LinearClient) GetIssue(identifier string) (*LinearIssue, error) {
	if !l.IsConfigured() {
		return nil, fmt.Errorf("LINEAR_API_KEY not set")
	}

	query := `
		query ($identifier: String!) {
			issue(id: $identifier) {
				id
				identifier
				title
				description
				state { name }
				priority
				url
				labels { nodes { name } }
				assignee { name }
				createdAt
				updatedAt
			}
		}
	`

	variables := map[string]interface{}{
		"identifier": identifier,
	}

	result, err := l.graphQL(query, variables)
	if err != nil {
		return nil, err
	}

	issueData, ok := result["issue"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("issue not found: %s", identifier)
	}

	return l.parseIssue(issueData), nil
}

// ListIssues lists issues assigned to the current user
func (l *LinearClient) ListIssues(teamKey string, limit int) ([]*LinearIssue, error) {
	if !l.IsConfigured() {
		return nil, fmt.Errorf("LINEAR_API_KEY not set")
	}

	query := `
		query ($first: Int!, $teamKey: String) {
			issues(first: $first, filter: { team: { key: { eq: $teamKey } } }) {
				nodes {
					id
					identifier
					title
					description
					state { name }
					priority
					url
					labels { nodes { name } }
					assignee { name }
					createdAt
					updatedAt
				}
			}
		}
	`

	variables := map[string]interface{}{
		"first":   limit,
		"teamKey": teamKey,
	}

	result, err := l.graphQL(query, variables)
	if err != nil {
		return nil, err
	}

	issuesData, ok := result["issues"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("failed to get issues")
	}

	nodes, ok := issuesData["nodes"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("failed to get issues nodes")
	}

	issues := make([]*LinearIssue, len(nodes))
	for i, node := range nodes {
		if issueMap, ok := node.(map[string]interface{}); ok {
			issues[i] = l.parseIssue(issueMap)
		}
	}

	return issues, nil
}

// UpdateIssueState updates an issue's state
func (l *LinearClient) UpdateIssueState(issueID, stateID string) error {
	if !l.IsConfigured() {
		return fmt.Errorf("LINEAR_API_KEY not set")
	}

	mutation := `
		mutation ($issueId: String!, $stateId: String!) {
			issueUpdate(id: $issueId, input: { stateId: $stateId }) {
				success
			}
		}
	`

	variables := map[string]interface{}{
		"issueId": issueID,
		"stateId": stateID,
	}

	_, err := l.graphQL(mutation, variables)
	return err
}

// AddComment adds a comment to an issue
func (l *LinearClient) AddComment(issueID, body string) error {
	if !l.IsConfigured() {
		return fmt.Errorf("LINEAR_API_KEY not set")
	}

	mutation := `
		mutation ($issueId: String!, $body: String!) {
			commentCreate(input: { issueId: $issueId, body: $body }) {
				success
			}
		}
	`

	variables := map[string]interface{}{
		"issueId": issueID,
		"body":    body,
	}

	_, err := l.graphQL(mutation, variables)
	return err
}

func (l *LinearClient) graphQL(query string, variables map[string]interface{}) (map[string]interface{}, error) {
	payload := map[string]interface{}{
		"query":     query,
		"variables": variables,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", linearAPIURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", l.apiKey)

	resp, err := l.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %s", string(body))
	}

	var result struct {
		Data   map[string]interface{} `json:"data"`
		Errors []struct {
			Message string `json:"message"`
		} `json:"errors"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	if len(result.Errors) > 0 {
		return nil, fmt.Errorf("GraphQL error: %s", result.Errors[0].Message)
	}

	return result.Data, nil
}

func (l *LinearClient) parseIssue(data map[string]interface{}) *LinearIssue {
	issue := &LinearIssue{}

	if v, ok := data["id"].(string); ok {
		issue.ID = v
	}
	if v, ok := data["identifier"].(string); ok {
		issue.Identifier = v
	}
	if v, ok := data["title"].(string); ok {
		issue.Title = v
	}
	if v, ok := data["description"].(string); ok {
		issue.Description = v
	}
	if v, ok := data["url"].(string); ok {
		issue.URL = v
	}
	if v, ok := data["priority"].(float64); ok {
		issue.Priority = int(v)
	}
	if v, ok := data["createdAt"].(string); ok {
		issue.CreatedAt = v
	}
	if v, ok := data["updatedAt"].(string); ok {
		issue.UpdatedAt = v
	}

	// State
	if state, ok := data["state"].(map[string]interface{}); ok {
		if name, ok := state["name"].(string); ok {
			issue.State = name
		}
	}

	// Assignee
	if assignee, ok := data["assignee"].(map[string]interface{}); ok {
		if name, ok := assignee["name"].(string); ok {
			issue.Assignee = name
		}
	}

	// Labels
	if labels, ok := data["labels"].(map[string]interface{}); ok {
		if nodes, ok := labels["nodes"].([]interface{}); ok {
			for _, node := range nodes {
				if labelMap, ok := node.(map[string]interface{}); ok {
					if name, ok := labelMap["name"].(string); ok {
						issue.Labels = append(issue.Labels, name)
					}
				}
			}
		}
	}

	return issue
}
