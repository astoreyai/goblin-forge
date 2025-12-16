package integrations

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
)

// JiraClient handles Jira integration
type JiraClient struct {
	baseURL  string // e.g., "https://company.atlassian.net"
	email    string
	apiToken string
	client   *http.Client
}

// JiraIssue represents a Jira issue
type JiraIssue struct {
	Key         string   `json:"key"`
	ID          string   `json:"id"`
	Summary     string   `json:"summary"`
	Description string   `json:"description"`
	Status      string   `json:"status"`
	IssueType   string   `json:"issueType"`
	Priority    string   `json:"priority"`
	URL         string   `json:"url"`
	Labels      []string `json:"labels"`
	Assignee    string   `json:"assignee"`
	Reporter    string   `json:"reporter"`
	CreatedAt   string   `json:"created"`
	UpdatedAt   string   `json:"updated"`
}

// NewJiraClient creates a new Jira client
func NewJiraClient() *JiraClient {
	return &JiraClient{
		baseURL:  os.Getenv("JIRA_BASE_URL"),
		email:    os.Getenv("JIRA_EMAIL"),
		apiToken: os.Getenv("JIRA_API_TOKEN"),
		client:   &http.Client{},
	}
}

// IsConfigured checks if Jira is configured
func (j *JiraClient) IsConfigured() bool {
	return j.baseURL != "" && j.email != "" && j.apiToken != ""
}

// GetIssue fetches a Jira issue by key (e.g., "PROJ-123")
func (j *JiraClient) GetIssue(key string) (*JiraIssue, error) {
	if !j.IsConfigured() {
		return nil, fmt.Errorf("Jira not configured (set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)")
	}

	url := fmt.Sprintf("%s/rest/api/3/issue/%s", j.baseURL, key)
	resp, err := j.doRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	var result struct {
		ID     string `json:"id"`
		Key    string `json:"key"`
		Fields struct {
			Summary     string `json:"summary"`
			Description struct {
				Content []struct {
					Content []struct {
						Text string `json:"text"`
					} `json:"content"`
				} `json:"content"`
			} `json:"description"`
			Status struct {
				Name string `json:"name"`
			} `json:"status"`
			IssueType struct {
				Name string `json:"name"`
			} `json:"issuetype"`
			Priority struct {
				Name string `json:"name"`
			} `json:"priority"`
			Labels []string `json:"labels"`
			Assignee struct {
				DisplayName string `json:"displayName"`
			} `json:"assignee"`
			Reporter struct {
				DisplayName string `json:"displayName"`
			} `json:"reporter"`
			Created string `json:"created"`
			Updated string `json:"updated"`
		} `json:"fields"`
	}

	if err := json.Unmarshal(resp, &result); err != nil {
		return nil, fmt.Errorf("failed to parse issue: %w", err)
	}

	// Extract description text
	var description string
	for _, block := range result.Fields.Description.Content {
		for _, content := range block.Content {
			description += content.Text
		}
	}

	issue := &JiraIssue{
		Key:         result.Key,
		ID:          result.ID,
		Summary:     result.Fields.Summary,
		Description: description,
		Status:      result.Fields.Status.Name,
		IssueType:   result.Fields.IssueType.Name,
		Priority:    result.Fields.Priority.Name,
		Labels:      result.Fields.Labels,
		Assignee:    result.Fields.Assignee.DisplayName,
		Reporter:    result.Fields.Reporter.DisplayName,
		CreatedAt:   result.Fields.Created,
		UpdatedAt:   result.Fields.Updated,
		URL:         fmt.Sprintf("%s/browse/%s", j.baseURL, result.Key),
	}

	return issue, nil
}

// ListIssues lists issues from a JQL query
func (j *JiraClient) ListIssues(jql string, limit int) ([]*JiraIssue, error) {
	if !j.IsConfigured() {
		return nil, fmt.Errorf("Jira not configured")
	}

	url := fmt.Sprintf("%s/rest/api/3/search", j.baseURL)

	payload := map[string]interface{}{
		"jql":        jql,
		"maxResults": limit,
		"fields":     []string{"summary", "status", "issuetype", "priority", "labels", "assignee"},
	}

	jsonData, _ := json.Marshal(payload)
	resp, err := j.doRequest("POST", url, jsonData)
	if err != nil {
		return nil, err
	}

	var result struct {
		Issues []struct {
			ID     string `json:"id"`
			Key    string `json:"key"`
			Fields struct {
				Summary  string `json:"summary"`
				Status   struct{ Name string } `json:"status"`
				IssueType struct{ Name string } `json:"issuetype"`
				Priority struct{ Name string } `json:"priority"`
				Labels   []string `json:"labels"`
				Assignee struct{ DisplayName string } `json:"assignee"`
			} `json:"fields"`
		} `json:"issues"`
	}

	if err := json.Unmarshal(resp, &result); err != nil {
		return nil, err
	}

	issues := make([]*JiraIssue, len(result.Issues))
	for i, r := range result.Issues {
		issues[i] = &JiraIssue{
			Key:       r.Key,
			ID:        r.ID,
			Summary:   r.Fields.Summary,
			Status:    r.Fields.Status.Name,
			IssueType: r.Fields.IssueType.Name,
			Priority:  r.Fields.Priority.Name,
			Labels:    r.Fields.Labels,
			Assignee:  r.Fields.Assignee.DisplayName,
			URL:       fmt.Sprintf("%s/browse/%s", j.baseURL, r.Key),
		}
	}

	return issues, nil
}

// AddComment adds a comment to an issue
func (j *JiraClient) AddComment(key, body string) error {
	if !j.IsConfigured() {
		return fmt.Errorf("Jira not configured")
	}

	url := fmt.Sprintf("%s/rest/api/3/issue/%s/comment", j.baseURL, key)

	// Jira uses Atlassian Document Format
	payload := map[string]interface{}{
		"body": map[string]interface{}{
			"type":    "doc",
			"version": 1,
			"content": []map[string]interface{}{
				{
					"type": "paragraph",
					"content": []map[string]interface{}{
						{
							"type": "text",
							"text": body,
						},
					},
				},
			},
		},
	}

	jsonData, _ := json.Marshal(payload)
	_, err := j.doRequest("POST", url, jsonData)
	return err
}

// TransitionIssue transitions an issue to a new status
func (j *JiraClient) TransitionIssue(key, transitionID string) error {
	if !j.IsConfigured() {
		return fmt.Errorf("Jira not configured")
	}

	url := fmt.Sprintf("%s/rest/api/3/issue/%s/transitions", j.baseURL, key)

	payload := map[string]interface{}{
		"transition": map[string]string{
			"id": transitionID,
		},
	}

	jsonData, _ := json.Marshal(payload)
	_, err := j.doRequest("POST", url, jsonData)
	return err
}

// GetTransitions gets available transitions for an issue
func (j *JiraClient) GetTransitions(key string) (map[string]string, error) {
	if !j.IsConfigured() {
		return nil, fmt.Errorf("Jira not configured")
	}

	url := fmt.Sprintf("%s/rest/api/3/issue/%s/transitions", j.baseURL, key)
	resp, err := j.doRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	var result struct {
		Transitions []struct {
			ID   string `json:"id"`
			Name string `json:"name"`
		} `json:"transitions"`
	}

	if err := json.Unmarshal(resp, &result); err != nil {
		return nil, err
	}

	transitions := make(map[string]string)
	for _, t := range result.Transitions {
		transitions[t.Name] = t.ID
	}

	return transitions, nil
}

func (j *JiraClient) doRequest(method, url string, body []byte) ([]byte, error) {
	var req *http.Request
	var err error

	if body != nil {
		req, err = http.NewRequest(method, url, bytes.NewBuffer(body))
	} else {
		req, err = http.NewRequest(method, url, nil)
	}
	if err != nil {
		return nil, err
	}

	// Basic auth with API token
	auth := base64.StdEncoding.EncodeToString([]byte(j.email + ":" + j.apiToken))
	req.Header.Set("Authorization", "Basic "+auth)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := j.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(respBody))
	}

	return respBody, nil
}

// ParseIssueRef parses various Jira issue reference formats
func ParseJiraRef(ref string) (string, error) {
	// Standard format: PROJ-123
	re := regexp.MustCompile(`^[A-Z]+-\d+$`)
	if re.MatchString(ref) {
		return ref, nil
	}

	// URL format
	urlRe := regexp.MustCompile(`/browse/([A-Z]+-\d+)`)
	if matches := urlRe.FindStringSubmatch(ref); len(matches) == 2 {
		return matches[1], nil
	}

	return "", fmt.Errorf("invalid Jira issue reference: %s", ref)
}
