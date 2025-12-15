# Goblin Forge Makefile

# Build variables
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "0.1.0-dev")
COMMIT ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE ?= $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
LDFLAGS := -ldflags "-X main.Version=$(VERSION) -X main.Commit=$(COMMIT) -X main.BuildDate=$(BUILD_DATE)"

# Go variables
GOCMD := go
GOBUILD := $(GOCMD) build
GOTEST := $(GOCMD) test
GOGET := $(GOCMD) get
GOMOD := $(GOCMD) mod
GOFMT := gofmt
GOLINT := golangci-lint

# Binary names
BINARY_NAME := gforge
BINARY_PATH := ./bin/$(BINARY_NAME)

# Source files
SRC_DIRS := ./cmd/... ./internal/...

.PHONY: all build clean test test-unit test-integration coverage lint fmt deps dev install uninstall help

# Default target
all: lint test build

## Build

build: ## Build the binary
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p ./bin
	$(GOBUILD) $(LDFLAGS) -o $(BINARY_PATH) ./cmd/gforge

build-linux: ## Build for Linux
	@echo "Building $(BINARY_NAME) for Linux..."
	@mkdir -p ./bin
	GOOS=linux GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o ./bin/$(BINARY_NAME)-linux-amd64 ./cmd/gforge

build-all: ## Build for all platforms
	@echo "Building for all platforms..."
	@mkdir -p ./bin
	GOOS=linux GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o ./bin/$(BINARY_NAME)-linux-amd64 ./cmd/gforge
	GOOS=linux GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o ./bin/$(BINARY_NAME)-linux-arm64 ./cmd/gforge
	GOOS=darwin GOARCH=amd64 $(GOBUILD) $(LDFLAGS) -o ./bin/$(BINARY_NAME)-darwin-amd64 ./cmd/gforge
	GOOS=darwin GOARCH=arm64 $(GOBUILD) $(LDFLAGS) -o ./bin/$(BINARY_NAME)-darwin-arm64 ./cmd/gforge

## Development

dev: ## Run in development mode
	$(GOCMD) run ./cmd/gforge $(ARGS)

watch: ## Run with file watching (requires entr)
	@find . -name '*.go' | entr -r $(GOCMD) run ./cmd/gforge $(ARGS)

## Testing

test: ## Run all tests
	@echo "Running tests..."
	$(GOTEST) -v $(SRC_DIRS)

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	$(GOTEST) -v -short $(SRC_DIRS)

test-integration: ## Run integration tests
	@echo "Running integration tests..."
	$(GOTEST) -v -run Integration $(SRC_DIRS)

coverage: ## Run tests with coverage
	@echo "Running tests with coverage..."
	$(GOTEST) -v -coverprofile=coverage.out $(SRC_DIRS)
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

## Code Quality

lint: ## Run linter
	@echo "Running linter..."
	@if command -v $(GOLINT) >/dev/null 2>&1; then \
		$(GOLINT) run ./...; \
	else \
		echo "golangci-lint not installed, skipping lint"; \
	fi

fmt: ## Format code
	@echo "Formatting code..."
	$(GOFMT) -s -w .

vet: ## Run go vet
	@echo "Running go vet..."
	$(GOCMD) vet $(SRC_DIRS)

## Dependencies

deps: ## Download dependencies
	@echo "Downloading dependencies..."
	$(GOMOD) download

deps-update: ## Update dependencies
	@echo "Updating dependencies..."
	$(GOMOD) tidy
	$(GOGET) -u ./...
	$(GOMOD) tidy

## Installation

install: build ## Install to ~/.local/bin
	@echo "Installing $(BINARY_NAME) to ~/.local/bin..."
	@mkdir -p ~/.local/bin
	@cp $(BINARY_PATH) ~/.local/bin/$(BINARY_NAME)
	@chmod +x ~/.local/bin/$(BINARY_NAME)
	@echo "Installed! Make sure ~/.local/bin is in your PATH"

install-global: build ## Install to /usr/local/bin (requires sudo)
	@echo "Installing $(BINARY_NAME) to /usr/local/bin..."
	sudo cp $(BINARY_PATH) /usr/local/bin/$(BINARY_NAME)
	sudo chmod +x /usr/local/bin/$(BINARY_NAME)
	@echo "Installed!"

uninstall: ## Uninstall from ~/.local/bin
	@echo "Uninstalling $(BINARY_NAME)..."
	@rm -f ~/.local/bin/$(BINARY_NAME)
	@echo "Uninstalled!"

## Cleanup

clean: ## Clean build artifacts
	@echo "Cleaning..."
	@rm -rf ./bin
	@rm -f coverage.out coverage.html
	@echo "Clean!"

## Utilities

version: ## Show version info
	@echo "Version: $(VERSION)"
	@echo "Commit:  $(COMMIT)"
	@echo "Date:    $(BUILD_DATE)"

check-deps: ## Check if required dependencies are installed
	@echo "Checking dependencies..."
	@command -v go >/dev/null 2>&1 || { echo "go is required but not installed"; exit 1; }
	@command -v tmux >/dev/null 2>&1 || { echo "tmux is required but not installed"; exit 1; }
	@command -v git >/dev/null 2>&1 || { echo "git is required but not installed"; exit 1; }
	@echo "All dependencies satisfied!"

## Help

help: ## Show this help
	@echo "Goblin Forge - Multi-agent CLI Orchestrator"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
