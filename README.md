# README Generator

* [I. Project Overview](#i-project-overview)
* [II. Architecture / Design](#ii-architecture--design)
* [III. Prerequisites](#iii-prerequisites)
* [IV. Installation / Setup](#iv-installation--setup)
* [V. Usage](#v-usage)
* [VI. Infrastructure](#vi-infrastructure)
* [VII. Configuration](#vii-configuration)
  * [A. Prompt Engineering and Context Management](#a-prompt-engineering-and-context-management)
* [VIII. Project Structure](#viii-project-structure)
  * [A. Application Code](#a-application-code)
  * [B. Infrastructure as Code](#b-infrastructure-as-code)
* [IX. Limitations / Assumptions](#ix-limitations--assumptions)

## I. Project Overview

README Generator is an AI-powered CLI tool that automatically generates comprehensive README.md files for codebases. The tool analyzes a project's repository structure, source code, and Git history to produce well-structured, accurate documentation without requiring prior knowledge of the project.

The tool is designed for developers and technical teams who want to:
- Automatically generate standardized README files for their projects
- Update existing documentation based on code changes (incremental update mode)
- Ensure documentation accuracy by deriving information directly from code
- Maintain consistent documentation structure across multiple repositories
- Reduce manual documentation effort

## II. Architecture / Design

The README Generator is built as a Python-based AI agent system with the following components:

### Core Components

1. **AI Agent (Strands Framework)**
   - Uses AWS Bedrock with Claude Sonnet 4.5 as the inference model
   - Configured with extended read timeout (180 seconds) for large codebases
   - Equipped with custom tools for repository exploration and file manipulation
   - Maintains conversation state for interactive chat mode

2. **Custom Tools**
   - `get_tree`: Recursively explores directory structure with configurable depth
   - `write_readme_file`: Writes generated content to README.md at the project root
   - `file_read`: Reads and analyzes source files (provided by strands-agents-tools)

3. **Git Integration**
   - Detects changes since the last README.md update using Git history
   - Generates diff output to focus analysis on modified files
   - Enables incremental documentation updates rather than full regeneration

4. **Security Layer**
   - Path validation ensures the agent can only access files within the specified root directory
   - Prevents directory traversal attacks

5. **Session Management**
   - File-based session persistence for conversation history
   - Enables interactive chat mode for iterative refinement

### Workflow

1. User invokes CLI with project path and project name
2. Agent retrieves AWS Bedrock inference profile by name pattern (`{project_name}_{domain_name}`)
3. If named profile is not found, falls back to global Claude Sonnet 4.5 profile
4. System prompt is constructed from templates and optional organizational context
5. Git diff analysis identifies changes since last README update (if applicable)
6. Agent explores repository structure using `get_tree`
7. Agent reads relevant files to understand the project
8. Agent generates or updates README.md based on analysis
9. (Optional) User can enter chat mode to iteratively refine the documentation

### Change-Based Update Mode

The tool implements an intelligent incremental update strategy:
- When a README.md already exists and the repository is a Git repository
- The tool extracts the diff of all changes since the README was last modified
- The AI agent focuses its analysis on changed files rather than re-analyzing the entire codebase
- This improves performance and reduces API costs for large repositories

## III. Prerequisites

### Required
- **Python**: 3.13 or higher
- **AWS Account**: With access to AWS Bedrock
- **AWS Credentials**: Properly configured on the local machine (via `~/.aws/credentials` or environment variables)
- **Poetry**: For dependency management
- **Terraform**: 1.0+ (for infrastructure deployment)

### AWS Permissions
The executing user/role must have permissions to:
- Call AWS Bedrock inference profiles (`bedrock:InvokeModel`)
- List AWS Bedrock inference profiles (`bedrock:ListInferenceProfiles`)

### Infrastructure Prerequisite
Before using the tool, an AWS Bedrock inference profile must be deployed via Terraform (see Infrastructure section). If the named profile is not found, the tool will attempt to use a default global Claude Sonnet 4.5 profile.

## IV. Installation / Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd readme-generator
```

### 2. Install Dependencies

Navigate to the code directory and install Python dependencies using Poetry:

```bash
cd code
poetry install
```

### 3. Configure AWS Credentials

Ensure AWS credentials are configured:

```bash
aws configure
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-west-1"
```

### 4. Deploy Infrastructure

Deploy the AWS Bedrock inference profile:

```bash
cd ../iac
terraform init -backend-config="bucket=<your-s3-bucket>" \
               -backend-config="dynamodb_table=<your-dynamodb-table>"
terraform apply -var="project_name=<your-project-name>" \
                -var="git_repository=<repository-url>"
```

The inference profile name will be: `{project_name}_readme_generator`

## V. Usage

### Basic Usage

Generate a README.md for the current directory:

```bash
poetry run readme_generator -p <project-name>
```

Generate a README.md for a specific path:

```bash
poetry run readme_generator -p <project-name> -r /path/to/project
```

### Interactive Chat Mode

Enable chat mode to iteratively refine the generated README:

```bash
poetry run readme_generator -p <project-name> -r /path/to/project --chat-mode
```

In chat mode:
- The tool generates an initial README.md
- You can provide feedback and request modifications
- Type `exit` to finish

### Providing Custom Context

The README Generator supports two methods for providing additional context to guide the documentation generation process.

#### Via Context File (Recommended for Organizations)

Use `--additional-context-file-path` to provide a file containing organizational or project-specific context:

```bash
poetry run readme_generator -p <project-name> -r /path/to/project \
    --additional-context-file-path /path/to/organizational-context.md
```

**Use cases for context files:**
- **Organizational Standards**: Define company-wide conventions, naming patterns, infrastructure practices, or deployment workflows
- **Technology Stack Context**: Specify internal frameworks, libraries, or tools used across multiple projects
- **Documentation Standards**: Enforce specific documentation styles, required sections, or terminology
- **Cloud & Infrastructure Conventions**: Document AWS account structures, resource naming conventions, tagging policies, or FinOps practices
- **Security & Compliance**: Include security guidelines, compliance requirements, or access control patterns

**Example context file** (`organizational-context.md`):
```markdown
# Company XYZ Technical Context

## Infrastructure Conventions
- All projects use AWS in eu-west-1 region
- Resource naming: {project}_{domain}_{stage}_{resource}
- All resources must have cost allocation tags

## Deployment
- GitLab CI/CD is the standard platform
- Terraform manages all infrastructure
- Backend state stored in S3 with DynamoDB locking

## Technology Stack
- Python projects use Poetry for dependency management
- All APIs follow OpenAPI 3.0 specification
- Monitoring uses CloudWatch and DataDog
```

This context will be injected into the AI agent's system prompt, ensuring generated documentation reflects organizational practices and conventions.

#### Via Context String (Quick Additions)

For simple, one-off context additions, use `-c` or `--additional-context-string`:

```bash
poetry run readme_generator -p <project-name> -r /path/to/project \
    -c "This is a legacy project migrated from Python 2.7 to Python 3.13"
```

### CLI Options

| Option | Required | Description |
|--------|----------|-------------|
| `-p, --project-name` | Yes | AWS project name (used to locate Bedrock inference profile) |
| `-r, --root-path` | No | Root path of the project to document (defaults to current directory) |
| `--chat-mode` | No | Enable interactive chat mode for README refinement |
| `--additional-context-file-path` | No | Path to file containing additional context for the AI (e.g., organizational conventions) |
| `-c, --additional-context-string` | No | Additional context provided as a string (for quick additions) |

## VI. Infrastructure

### Overview

The infrastructure is managed with Terraform and deploys an AWS Bedrock inference profile.

### Terraform Resources

**File**: `iac/bedrock_inference_profile.tf`

- **aws_bedrock_inference_profile.main**: Creates a Bedrock inference profile
  - Name pattern: `{project_name}_readme_generator`
  - Model: Claude Sonnet 4.5 (`global.anthropic.claude-sonnet-4-5-20250929-v1:0`)
  - Uses global inference profile for cross-region availability

### Terraform Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `project_name` | Name of the project (used for resource naming) | Yes |
| `git_repository` | Git repository URL (used for tagging) | Yes |
| `role_to_assume_arn` | ARN of IAM role to assume for deployment | No |

### Deployment Workflow

#### GitLab CI/CD (Organizational Standard)

The project uses GitLab CI/CD for automated deployment:

- **CI/CD Configuration**: `.gitlab-ci.yml`
- **Shared Templates**: Includes reusable templates from `erwan.simon/devops-platform-ci-templates` (v2.0.2)
- **Pipeline Stages**: init, format, security, deploy, release, mirror_to_github
- **Environment Selection**: Derived from Git branch name (`$CI_COMMIT_REF_SLUG`)
- **Project Variables**:
  - `PROJECT_NAME`: poc
  - `DOMAIN_NAME`: readme_generator
  - `STAGE_NAME`: Automatically set from branch name

#### Local Deployment

For local Terraform execution:

1. Initialize Terraform with backend configuration:
   ```bash
   terraform init -backend-config="bucket=<s3-bucket>" \
                  -backend-config="dynamodb_table=<dynamodb-table>"
   ```

2. Create or select Terraform workspace (controls environment):
   ```bash
   # Create new environment workspace
   terraform workspace new prod
   
   # Or select existing workspace
   terraform workspace select prod
   ```
   
   **Note**: If no workspace is created, Terraform uses the `default` workspace, resulting in `stage_name=default`.

3. Apply Terraform configuration:
   ```bash
   terraform apply -var="project_name=poc" \
                   -var="git_repository=https://gitlab.com/your/repo"
   ```

4. Verify AWS credentials target the correct account:
   ```bash
   aws sts get-caller-identity
   ```

### Backend Configuration

- **Backend Type**: S3
- **State File Key**: `readme_generator.tfstate`
- **Region**: `eu-west-1`
- **Encryption**: Enabled

Backend configuration is provided at runtime (not hardcoded in Terraform files), following organizational conventions.

### Tagging

All AWS resources are tagged with:
- `Appli`: Project name
- `Component`: `readme_generator`
- `git_repository`: Source repository URL

These tags support cost allocation and FinOps tracking.

## VII. Configuration

### Environment Variables

The tool does not require environment variables for basic operation, but relies on standard AWS SDK credential resolution:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION` (defaults to `eu-west-1` in Terraform)

### Configuration Files

#### System Prompt (`code/readme_generator/system_prompt.txt`)
Defines the AI agent's behavior, analysis guidelines, and README structure requirements. This file is loaded at runtime and combined with the README template.

Key instructions include:
- Agent role and constraints
- Repository analysis methodology
- **Change-based update mode**: Instructions for incremental updates based on Git diff
- **Context window safety**: Adaptive exploration strategy to prevent token overflow
- **Documentation neutrality rule**: Ensures README represents current state without mentioning changes or versions
- README content requirements
- Organizational context awareness
- Output behavior and feedback loop handling

#### README Template (`code/readme_generator/readme_example.md`)
Defines the expected structure and sections for generated README files.

### Project Configuration

**File**: `code/pyproject.toml`

- **Package Name**: `readme_generator`
- **Version**: 0.5.1
- **Python Version**: ^3.13
- **Entry Point**: `readme_generator` command mapped to `readme_generator.main:command_line_main`

### Inference Profile Resolution

The tool looks up the Bedrock inference profile using the pattern:
```
{project_name}_{domain_name}
```
Where:
- `project_name`: Provided via `-p` CLI option
- `domain_name`: Fixed to `readme_generator`

Example: `-p poc` resolves to inference profile `poc_readme_generator`

If the named profile is not found, the tool falls back to:
```
arn:aws:bedrock:{region}:{account}:inference-profile/global.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Bedrock Configuration

The Bedrock client is configured with:
- **Read Timeout**: 180 seconds (to accommodate large repository analysis)
- **Model**: Claude Sonnet 4.5 via inference profile
- **Session Management**: File-based persistence for conversation history

### A. Prompt Engineering and Context Management

The README Generator constructs the AI agent's system prompt by combining multiple sources in the following order:

#### 1. Base System Prompt (`system_prompt.txt`)

The foundation of the agent's instructions, defining:
- The agent's role as a senior software engineer and technical writer
- Analysis methodology and constraints
- Required README sections and structure
- Output format and tone guidelines
- Security constraints (e.g., respecting `.gitignore`, file access boundaries)
- **Organizational context awareness**: Explicit instruction that "Organizational context is authoritative unless explicitly contradicted by the repository"
- **Change-based update mode**: Instructions for using Git diff to focus on modified files
- **Documentation neutrality rule**: Prohibition of version references or "new/added/removed" language
- **Context window safety**: Adaptive directory-by-directory exploration strategy

#### 2. README Template (`readme_example.md`)

Appended to the system prompt to provide a structural template with:
- Standard section headings and hierarchy
- Table of contents format
- Markdown conventions

#### 3. Organizational Context (Optional)

Injected via `--additional-context-file-path`, this is where you can provide:
- Company-wide technical conventions
- Infrastructure and deployment standards
- Naming conventions and tagging policies
- Technology stack preferences
- Compliance and security requirements
- CI/CD platform and execution model
- Cloud provider conventions and region preferences

This ensures the AI agent interprets repositories through the lens of your organization's specific practices, producing documentation that aligns with internal standards.

#### 4. User-Provided Context String (Optional)

Any additional context provided via `--additional-context-string` is appended:
```python
system_prompt += "\nFinally, the user gave you this sentence as additional context:" + user_string
```

#### 5. Git Diff List (Automatic)

If the repository is a Git repository and a README.md exists, the tool automatically appends:
```python
system_prompt += "\n\nHere is the diff list:\n" + str(changes_list)
```

This enables the agent to focus on changed files and perform incremental updates.

#### Prompt Construction Flow

```
Final System Prompt = Base Instructions (with org context awareness)
                    + README Template 
                    + [Organizational Context File] 
                    + [User Context String]
                    + [Git Diff Since Last README Update]
```

This layered approach allows for:
- **Consistency**: Base prompt ensures standard behavior across all runs
- **Organizational Alignment**: System prompt explicitly prioritizes organizational context
- **Customization**: Organizational context adapts the tool to your environment
- **Flexibility**: User context string enables quick, one-off adjustments
- **Efficiency**: Git diff enables incremental updates for large repositories

#### Best Practices for Context Files

1. **Keep it factual**: Provide objective information about conventions, not preferences
2. **Be specific**: Include concrete examples of naming patterns, resource structures, etc.
3. **Document CI/CD and deployment**: Specify which platform is used (GitLab CI, GitHub Actions, etc.) and how environments are selected
4. **Include infrastructure conventions**: Cloud provider, region, Terraform backend patterns, workspace usage
5. **Update regularly**: Maintain the context file as organizational practices evolve
6. **Version control**: Store organizational context files in a shared repository
7. **Scope appropriately**: Separate general organizational context from project-specific details

## VIII. Project Structure

```
readme-generator/
├── code/                           # Python application code
│   ├── readme_generator/           # Main package
│   │   ├── main.py                 # CLI entry point and agent orchestration
│   │   ├── system_prompt.txt       # AI agent instructions
│   │   └── readme_example.md       # README template structure
│   ├── pyproject.toml              # Poetry configuration and dependencies
│   └── poetry.lock                 # Locked dependency versions
├── iac/                            # Infrastructure as Code (Terraform)
│   ├── bedrock_inference_profile.tf # Bedrock inference profile resource
│   ├── locals.tf                   # Local variables
│   ├── variables.tf                # Input variables
│   ├── data.tf                     # Data sources (AWS account, region)
│   ├── terraform.tf                # Provider and backend configuration
│   └── backend.hcl                 # Backend configuration (git-ignored)
├── .gitlab-ci.yml                  # GitLab CI/CD pipeline
├── .releaserc.json                 # Semantic release configuration
├── .gitignore                      # Git ignore patterns
└── LICENSE                         # MIT License
```

### A. Application Code

**`code/readme_generator/main.py`**
- CLI entry point using Click framework
- Agent initialization and orchestration
- Custom tool definitions (`get_tree`, `write_readme_file`)
- Security validation for file access
- Chat mode implementation
- Prompt construction logic (base + template + organizational context + user context + git diff)
- Git integration for change detection (`get_git_diff_since_readme_update`)
- Bedrock client configuration with extended read timeout (180 seconds)
- Inference profile resolution with fallback to global profile

**`code/readme_generator/system_prompt.txt`**
- Defines AI agent role and capabilities
- Specifies analysis guidelines
- Lists required README sections
- Sets output format and tone
- **Includes organizational context awareness directive**: "Organizational context is authoritative unless explicitly contradicted by the repository"
- **Includes organizational context exposure guideline**: "When organizational conventions materially affect how users build, deploy, or operate the project, they MUST be explicitly documented in the README"
- **Defines change-based update mode**: Instructions for using Git diff to focus analysis
- **Defines documentation neutrality rule**: Prohibition of version/change references
- **Defines context window safety strategy**: Adaptive directory-by-directory exploration

**`code/readme_generator/readme_example.md`**
- Markdown template for generated READMEs
- Defines standard section structure

### B. Infrastructure as Code

**`iac/bedrock_inference_profile.tf`**
- Defines AWS Bedrock inference profile resource
- Configures Claude Sonnet 4.5 model
- Uses global inference profile for cross-region support

**`iac/locals.tf`**
- `domain_name`: Fixed to `readme_generator`
- `environment_name`: Computed as `{project_name}_{domain_name}`

**`iac/terraform.tf`**
- AWS provider configuration with default tags
- S3 backend configuration for state management
- IAM role assumption support

## IX. Limitations / Assumptions

### Assumptions

1. **AWS Region**: Infrastructure defaults to `eu-west-1` (Ireland)
2. **Python Version**: Requires Python 3.13 or higher
3. **Bedrock Access**: Assumes AWS account has access to Claude Sonnet 4.5 model
4. **Terraform Backend**: Backend configuration must be provided at initialization time (not hardcoded)
5. **GitLab CI/CD**: CI/CD pipelines are configured for GitLab (not GitHub Actions)
6. **Inference Profile Naming**: The tool expects inference profiles to follow the naming pattern `{project_name}_readme_generator`
7. **GitHub Mirror**: This repository is mirrored to GitHub from GitLab (source of truth is GitLab)
8. **Git Repository**: Change-based update mode requires the project to be a Git repository

### Limitations

1. **Path Restriction**: The agent can only access files within the specified root path (security measure)
2. **Recursive Depth**: Directory exploration is limited to a configurable depth (default: 5 levels) to prevent performance issues
3. **Model Dependency**: Requires access to AWS Bedrock and the specific Claude model
4. **AWS Credentials**: Relies on locally configured AWS credentials (does not support credential injection)
5. **Single Repository Analysis**: Designed to analyze one repository at a time
6. **No Multi-language LLM Support**: Currently configured only for Claude on AWS Bedrock
7. **GitIgnore Awareness**: The system prompt instructs the agent to respect `.gitignore`, but enforcement depends on AI behavior
8. **Read Timeout**: Bedrock API calls are subject to 180-second timeout, which may affect very large repositories

### Known Constraints

- **Token Limits**: Large codebases may exceed Claude's context window; the tool implements adaptive exploration to mitigate this
- **Cost**: Each README generation incurs AWS Bedrock API costs
- **Network Dependency**: Requires network access to AWS services
- **Session Persistence**: Chat mode sessions are stored locally and not shared across machines
- **Terraform Workspace**: Local users must manually create and select Terraform workspaces to control environment (`stage_name`); otherwise defaults to `default` workspace
- **Git Diff Analysis**: Change-based update mode is only available for Git repositories with existing README.md files
- **Inference Profile Fallback**: If the named inference profile is not found, the tool uses a global profile ARN which may have different rate limits or availability
