# Indic FactCheck Framework

This repository contains a data collection and phrase-extraction workflow for building an Indic-language fact-checking dataset.

## Structure

- .Data_Collection/: scraper and dataset files for collecting fact-check claims
- .vscode/: editor workspace settings

## Setup

1. Create and activate a Python environment.
2. Install required dependencies if needed.
3. Set the FactCheck API key before running the scraper:
   ```bash
   set FACTCHECK_API_KEY=your-key-here
   python .Data_Collection/factcheck_scraper.py
   ```

## Notes

The scraper uses the Google Fact Check Tools API and writes CSV outputs into the data collection folder.
# Sakshya-Indian-Fact-Verification-System
