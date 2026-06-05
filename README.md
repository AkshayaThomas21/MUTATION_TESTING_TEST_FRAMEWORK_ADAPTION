# Mutation Test AI

An AI-powered mutation testing tool for C projects using GTest. It uses LLM agents (via Azure OpenAI) to generate, filter, and rank code mutants — then compiles and runs them against your existing test suite to measure how well your tests actually catch bugs.

---

## What It Does

Traditional mutation testing tools apply dumb, mechanical changes to code (flip an operator, swap a constant). This tool is different — it uses a multi-agent LLM pipeline to generate **smart, context-aware mutants** that are specifically designed to survive your test suite. The ones that survive point directly at gaps in your test coverage.

The pipeline:
1. Parses your C source file and extracts functions
2. Extracts existing GTest test cases
3. Generates mutants using LLM agents (with reflection loops)
4. Filters out equivalent mutants and hallucinated code
5. Clones the project, injects each mutant, builds, and runs tests
6. Classifies results (killed / survived / build error)
7. Produces an HTML report with mutation scores

---

## Prerequisites

- **Python 3.11+**
- **Azure OpenAI** access (you need an endpoint, API key, and deployment name)
- A C project with GTest-based unit tests
- A build script (`.cmd`) that compiles and runs the tests for your project
- `cmd.exe` available (Windows)

---

## Setup

### 1. Copy this repo

```
unzip Mutation_Test_AI.7z
cd Mutation_Test_AI
```

### 2. Create a virtual environment and install dependencies

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up your `.env` file

Create a `.env` file in the project src with your Azure OpenAI credentials:

```
LLM_FARM_API_KEY=your-api-key-here
AZURE_DEPLOYMENT=your-deployment-name
AZURE_API_VERSION=2024-02-15-preview
AZURE_ENDPOINT=https://your-endpoint.openai.azure.com/
```

### 4. Configure `config.yaml`

Edit `config.yaml` to point at your project:

```yaml
mutation:
  project_path_folder: C:/path/to/your/project
  source_file: C:/path/to/your/project/src/YourFile.c
  test_case_folder: C:/path/to/your/project/tests/Testcases
  output_dir: mutants_output
  recursion_limit: 2
  script_path: C:/path/to/your/run_tests.cmd
```

| Field | What it is |
|---|---|
| `project_path_folder` | Root of your C project (gets cloned per mutant) |
| `source_file` | The `.c` file you want to mutation-test |
| `test_case_folder` | Folder containing your GTest test files |
| `output_dir` | Where the mutant JSON files get saved |
| `recursion_limit` | How many generate→reflect loops the LLM does (default: 2) |
| `script_path` | A `.cmd` script that builds and runs tests from the project root |

### 5. Build script requirements

Your build/test script (`script_path`) should:
- Accept the working directory as its `cwd`
- Optionally read a `TEST_TARGET` environment variable to know which test binary to run
- Return exit code 0 on test pass, non-zero on failure
- Ideally produce an XML test report (the tool looks for `<function_name>.xml`)

---

## Usage

### Quick start

```
python Mutation_Test.py
```

Or use the batch wrapper:

```
Mutation_Test.cmd
```

### What happens when you run it

1. The tool reads `config.yaml` and extracts all functions from your source file using tree-sitter
2. It lists the functions and asks you to pick which ones to test:
   ```
   [INFO] Found 12 functions:
   ----------------------------------------
     1 : FunctionA
     2 : FunctionB
     3 : FunctionC
   ----------------------------------------
   Enter function numbers to process (comma-separated, or 'all' for all):
   ```
3. Type `1,3` to pick specific functions, or `all` to process everything
4. The pipeline runs end-to-end and prints a summary when done

### Custom config path

```
python Mutation_Test.py --config path/to/other_config.yaml
```

---

## How It Works — The Full Pipeline Flow

Here's what happens under the hood, step by step:

```
Mutation_Test.py (entry point)
  │
  ├── Reads config.yaml
  ├── Extracts functions from source .c file (tree-sitter)
  ├── User selects functions
  │
  └── Calls pipeline.run_mutation_pipeline()
        │
        ├── 1. EXTRACT phase
        │     ├── Extract functions → functions_dict
        │     ├── Extract test cases → test_cases_dict  
        │     └── Build dependency map → dependency_dict
        │
        ├── 2. GENERATE phase (per function)
        │     │
        │     ├── Source Analyzer Agent
        │     │     Reads the full source, understands context,
        │     │     produces a summary for other agents
        │     │
        │     ├── Test Case Analyzer Agent
        │     │     Finds gaps and weak spots in existing tests,
        │     │     produces hints for the mutant generator
        │     │
        │     ├── Mutation Generator Agent
        │     │     Creates 6-7 mutants per iteration using hints
        │     │     and feedback from previous rounds
        │     │
        │     └── Reflector Agent (loop)
        │           Reviews generated mutants, gives feedback,
        │           loops back to generator (up to recursion_limit)
        │
        ├── 3. FILTER phase (per function)
        │     │
        │     ├── Equivalent Checker Agent
        │     │     Removes mutants that are semantically identical
        │     │     to the original code
        │     │
        │     └── Hallucination Checker Agent
        │           Removes mutants that reference non-existent
        │           variables, functions, or invalid syntax
        │
        ├── 4. BUILD & TEST phase
        │     ├── Clone the entire project (once per mutant)
        │     ├── Inject mutated code into the clone
        │     ├── Build and run tests (parallel, 4 workers)
        │     └── Capture build logs and test results
        │
        ├── 5. CLASSIFY phase
        │     ├── Parse logs and XML test reports
        │     ├── Mark each mutant: Killed / Survived / Build-error
        │     └── Calculate mutation score
        │
        └── 6. REPORT phase
              ├── Per-function JSON reports → temp/c1.json, c2.json...
              └── Combined HTML report → temp/mutation_report.html
```

### The LLM Agent Graph (LangGraph)

The mutant generation uses a LangGraph state machine:

```
START
  → Source Analyzer Agent
  → Test Case Analyzer Agent
  → Mutation Generator Agent
  → (if steps < recursion_limit) → Reflector Agent → back to Generator
  → END
```

Each agent is a separate LLM call with structured output (Pydantic models). The reflector creates a feedback loop — it critiques the generated mutants and sends improvement suggestions back to the generator for the next round.

---

## Project Structure

```
Mutation_Test_AI/
│
├── Mutation_Test.py          # Entry point — config loading, user interaction
├── Mutation_Test.cmd          # Batch wrapper for quick runs
├── pipeline.py                # Main pipeline orchestration
├── config.yaml                # Project paths and settings
├── requirements.txt           # Python dependencies
│
├── core/                      # Low-level utilities
│   ├── function_extractor.py  # Parses C files with tree-sitter
│   ├── testcase_extractor.py  # Extracts GTest test blocks
│   ├── gtest_runner.py        # Cloning, building, test execution, reporting
│   ├── middleware.py          # Glue between extraction and pipeline
│   └── file_operations.py     # File I/O helpers
│
├── src/                       # LLM agent layer
│   ├── agents.py              # All agent classes (Generator, Reflector, etc.)
│   ├── graph.py               # LangGraph workflow definition
│   ├── prompts.py             # Prompt templates for each agent
│   ├── llm_runnable.py        # Azure OpenAI client wrapper
│   ├── data_classes.py        # Pydantic models (Mutant, State, Output)
│   ├── .env                   # .env with valid credentials
│   └── utils.py               # Formatting/stringification helpers
│
├── clones/                    # Temporary project clones (one per mutant)
├── logs/                      # Build/test logs per clone
├── temp/                      # Intermediate JSON reports + final HTML report
├── intermediate/              # Source context, feedback, hallucination logs
├── mutants_output/            # Persisted mutant JSON files
└── equivalents/               # Logged equivalent mutants
```

---

## Output

After a run, you'll find:

| Location | What's there |
|---|---|
| `temp/mutation_report.html` | The main report — open in a browser |
| `temp/c1.json`, `c2.json`... | Per-function results with mutant details |
| `mutants_output/mutants_<timestamp>.json` | Raw generated mutants before testing |
| `equivalents/` | Mutants flagged as equivalent |
| `logs/` | Raw build/test output per clone |

### Mutation score

```
Mutation Score = (Killed Mutants) / (Killed + Survived) × 100%
```

- **Killed** — test suite caught the mutant (good)
- **Survived** — mutant slipped through (your tests have a gap here)
- **Build-error** — mutant broke compilation (excluded from score)

---

## Troubleshooting

**"Source file not found"**  
Check `source_file` in `config.yaml`. Must be an absolute path to an existing `.c` file.

**"No .c test file found"**  
The `test_case_folder` must contain at least one `.c` file with your GTest tests.

**All mutants are build errors**  
Your build script might not be compatible. Make sure it runs correctly when called as:
```
cmd.exe /c <script_path>
```
from your project's root directory.

**LLM returns empty or garbage**  
Check your `.env` credentials. Make sure the Azure deployment supports function calling / structured output.

**Pipeline is slow**  
Each mutant requires a full project clone + build + test cycle. Reduce the number of functions or lower `recursion_limit` to speed things up. The tool runs 4 clones in parallel by default.
