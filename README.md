# D.O.P.E. – Desktop Organizing & Polishing Engine

A desktop organization tool that uses AI (via web interface, no API key needed) to automatically restructure your messy files into a balanced directory tree, making files easier to locate.

## Why D.O.P.E.?

- **Zero Setup**: No API keys or local LLM setup needed - just use Claude's web interface
- **Smart Organization**: Uses AI to create a balanced directory tree structure
- **Safe to Use**: Built-in rollback for all changes
- **Platform**: Works on macOS (Windows support planned)

## Quick Usage

1. Run plan mode to analyze your desktop:
   ```bash
   python main.py --desktop ~/Desktop --plan-file desktop.plan --mode plan
   ```

2. Upload the generated `desktop.plan.prompt` file to Claude and get the reorganization plan
   - Copy the entire contents of the prompt file
   - Paste it to Claude
   - Copy Claude's response to `desktop.plan`

3. Execute the plan:
   ```bash
   python main.py --desktop ~/Desktop --plan-file desktop.plan --mode execute
   ```

4. Review the changes and:
   - Type 'y' to confirm and make changes permanent
   - Type 'n' to rollback all changes

Note: A rollback file (.rollbackinfo.json) is automatically created during execution and removed after confirmation or rollback.