# CLAUDE.md - FindJobAgent (V7.1 Architecture)

## Context and docs
- Before coding, head to the `D:\programming_enviroment\findJobAgent\docs\` path to check the req docs, tech stack, project directory, and database design.

## Commands
- **Backend (Python - Windows)**:
  - **Context Rule**: Execute from Project Root (D:\programming_enviroment\findJobAgent).
  - **Interpreter**: `backend\.venv\Scripts\python.exe`
  - **Why not Activate.ps1?**: We call the venv python directly to ensure the environment is used every time without activation scripts.
  - Run App: `backend\.venv\Scripts\python.exe backend\run.py`
  - Run Tests: `backend/.venv/Scripts/python.exe -m pytest backend/tests -v`
  - Run Single Test: `backend/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_file.py::TestClass::test_method -v`
  - **Dependency Mgmt**:
    - Install All: `backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt`
    - Add New Lib: `backend\.venv\Scripts\python.exe -m pip install <lib>; backend\.venv\Scripts\python.exe -m pip freeze > backend\requirements.txt`
    - *Strict Rule*: Only use `pip` + `venv`. No Poetry/Conda.

**IMPORTANT**: Use forward slashes (/) in paths for consistent cross-platform compatibility in commands.

- **Frontend (Next.js - Windows)**:
  - **Context Rule**: Execute from Project Root.
  - Run Dev: `npm run dev --prefix frontend`
  - Install Deps: `npm install --prefix frontend`
  - *Strict Rule*: Mantine UI only. **NO Tailwind CSS**.

## Windows Bash Best Practices (Critical for Claude)

**Root Cause Analysis**: Bash command failures stem from:
- Windows path handling requiring `\` in paths but shell escaping demands attention
- Mixed Windows/Unix styles causing resolution issues
- Venv scripts are in `Scripts/` (not `bin`) on Windows
- Working directory critically affects relative path resolution

**Verified Success Patterns:**

1. **Execute from Project Root** (D:\programming_enviroment\findJobAgent):
   ```bash
   backend/.venv/Scripts/python.exe backend/run.py
   backend/.venv/Scripts/python.exe -m pytest backend/tests -v
   ```

2. **Use Project Root-Relative Paths** - never complex `../../../` navigation:
   ```bash
   # Right: from project root
   backend/.venv/Scripts/python.exe -c "..."

   # Wrong: complex relative paths that break context
   cd somewhere && ../../.venv/python.exe ...
   ```

3. **Avoid Chain Commands with &&** when path resolution changes:
   - Prefer separate single commands from stable directory
   - Each command's pwd affects the next chained command

4. **Python Module Discovery** - scripts run in backend/ need correct sys.path:
   ```python
   import sys
   sys.path.insert(0, '.')  # Makes 'app' discoverable
   # or use: sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
   ```

5. **File Operations** - Always prefer project-root relative paths:
   ```bash
   dir backend\app\models      # List models
   cat backend/app/models/*.py  # Read all model files
   ```

**Key Lesson**: Windows venv paths are extremely strict. The working directory when invoking `.venv/Scripts/python.exe` determines module discovery success. Always operate from project root using project-relative paths.

## Architecture (V7.1 Double Tower)
- **Root Strategy**: Monorepo Structure.
  - `/backend`: Core Agent (FastAPI + LangGraph).
  - `/frontend`: UI Console (Next.js + Fetch API).
- **Backend Logic Flow**:
  - Router -> Context Pruner -> Scorer -> Generator.
  - Database: SQLite (Local) + SQLModel.
- **Frontend Logic**:
  - Use Fetch API for SSE (Stream). **NO Axios**.

## Security Protocols (CRITICAL)
1.  **Zero Persistence**: **NEVER** create or write to `.env` files in this project.
2.  **Allowed Config**: You MAY read `backend\llm_config.json` for non-sensitive settings.
3.  **Hybrid Auth**: Combine `llm_config.json` (structure) + `os.environ` (secrets) to initialize models.
4.  **Secret Leakage**: Do not output API keys or passwords in the terminal.

## Code Style Guidelines
- **General**:
  - **NO EMOJIS**: Do not use emojis in source code, comments, or UI text.
- **Python**:
  - **Type Hints**: All function arguments and return values must be typed.
  - **Async**: Default to `async/await` for I/O operations.
- **TypeScript**:
  - Define explicit Interfaces matching backend Pydantic models. No `any`.

## Windows Bash Best Practices (Critical for Claude)

**Root Cause Analysis**: Bash command failures stem from:
- Windows path handling requiring `\` in paths but shell escaping demands attention
- Mixed Windows/Unix styles causing resolution issues
- Venv scripts are in `Scripts/` (not `bin`) on Windows
- Working directory critically affects relative path resolution

**Verified Success Patterns:**

1. **Execute from Project Root** (D:\programming_enviroment\findJobAgent):
   ```bash
   backend/.venv/Scripts/python.exe backend/run.py
   backend/.venv/Scripts/python.exe -m pytest backend/tests -v
   ```

2. **Use Project Root-Relative Paths** - never complex `../../../` navigation:
   ```bash
   # Right: from project root
   backend/.venv/Scripts/python.exe -c "..."

   # Wrong: complex relative paths that break context
   cd somewhere && ../../.venv/python.exe ...
   ```

3. **Avoid Chain Commands with &&** when path resolution changes:
   - Prefer separate single commands from stable directory
   - Each command's pwd affects the next chained command

4. **Python Module Discovery** - scripts run in backend/ need correct sys.path:
   ```python
   import sys
   sys.path.insert(0, '.')  # Makes 'app' discoverable
   # or use: sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
   ```

5. **File Operations** - Always prefer project-root relative paths:
   ```bash
   dir backend\app\models      # List models
   cat backend/app/models/*.py  # Read all model files
   ```

**Key Lesson**: Windows venv paths are extremely strict. The working directory when invoking `.venv/Scripts/python.exe` determines module discovery success. Always operate from project root using project-relative paths.

## Workflow Protocols
**When I use the keyword "Implement: <Feature>", strict adherence to this cycle is required:**

1.  **Phase 1: Blueprint (Plan)**
    - Analyze request. List files to modify.
    - *Action*: Output plan and wait for approval.

2.  **Phase 2: Red-Green Loop (Code & Test)**
    - **Step A (Test)**: Create/update test in `backend\tests\`.
    - **Step B (Verify Fail)**: Run test (must fail).
    - **Step C (Code)**: Write logic in `backend\app\`.
    - **Step D (Verify Pass)**: Run test (must pass).

3.  **Phase 3: Git Prep & Safety Net**
    - **Pre-commit Check**: Be aware that a hook will block commits if tests fail.
    - **Commit Strategy**: 
      - Propose `git commit` command.
      - **Language Rule**: Commit messages must be in **ENGLISH ONLY**.
      - **Format**: Conventional Commits (e.g., `feat(agent): add context pruner`).

## Beginner Learning Preferences
1.  **Explain the 'Why'**: Briefly explain root causes of bugs.
2.  **Step-by-Step**: One logical unit at a time.
3.  **Chinese Comments**: Critical business logic must have Chinese comments (but **NO EMOJIS**).