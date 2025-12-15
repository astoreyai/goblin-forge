# Screener (Archived)

This repository has been **archived** and replaced with a minimal implementation.

## New Location

**[icli-scanner](https://github.com/astoreyai/icli-scanner)** - 450 lines vs 26,000 lines

## Why Archived

The original screener was over-engineered for the requirement. Built a full trading platform (dashboard, database, positions, trailing stops) when only simple stock scanning was needed.

| Metric | Old (this repo) | New (icli-scanner) |
|--------|-----------------|-------------------|
| Lines of code | 26,000 | 450 |
| Modules | 32 | 1 |
| Tests | 662 | Minimal |
| Complexity | High | Low |

## Lessons Learned

1. **Start Simple** - Validate requirements before building
2. **YAGNI** - You Aren't Gonna Need It
3. **Early Feedback** - Ask "is this too much?" sooner
