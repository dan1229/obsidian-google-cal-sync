# Obsidian Google Calendar Sync
#### By: [Daniel Nazarian](https://www.danielnazarian.com) 🐧👹
##### Contact me at <dnaz@danielnazarian.com>

-------------------------------------------------------

## Description

This project provides automated synchronization between Google Calendar and Obsidian daily notes. It fetches events from multiple Google Calendar feeds and updates your Obsidian daily notes with formatted calendar sections.

## Components

### 1. GitHub Action Workflow (`calendar-sync.yml`)
- Runs automatically every 4 hours and can be triggered manually
- Sets up Python environment and required dependencies
- Executes the calendar sync script with secure environment variables
- Handles git operations to commit and push updates with retry logic

### 2. Calendar Sync Scripts

#### Main Script (`main.py`)
- Primary script for calendar synchronization
- Features:
  - Multi-calendar support with different labels/emojis
  - Smart event formatting with links to meetings/locations
  - Timezone handling
  - Recurring event support
  - Automatic emoji selection based on event keywords
  - Robust error handling and logging

#### Simple Version (`simply.py`)
- Minimal implementation for basic calendar sync
- Perfect for getting started or simpler use cases
- Features:
  - Single calendar support
  - Basic event formatting
  - Straightforward file handling


-------------------------------------------------------

##### Copyright © [Daniel Nazarian](https://danielnazarian.com)
