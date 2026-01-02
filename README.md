# README Generator

* [I. Project Overview](#i-project-overview)
* [II. Architecture / Design](#ii-architecture--design)
* [III. Prerequisites](#iii-prerequisites)
* [IV. Installation / Setup](#iv-installation--setup)
* [V. Usage](#v-usage)
* [VI. Infrastructure](#vi-infrastructure)
* [VII. Configuration](#vii-configuration)
* [VIII. Project Structure](#viii-project-structure)
  * [A. Application Code](#a-application-code)
  * [B. Infrastructure as Code](#b-infrastructure-as-code)
* [IX. Limitations / Assumptions](#ix-limitations--assumptions)

## I. Project Overview

README Generator is an AI-powered tool that automatically generates comprehensive README.md documentation for software projects. It uses AWS Bedrock's Claude Sonnet model to analyze a codebase and produce well-structured, professional documentation.

The tool is designed for developers who need to quickly create or update README files by leveraging AI to understand project structure, dependencies, and functionality through automated code analysis.

## II. Architecture / Design

The project consists of two main components:

1. **Python CLI Application**: An agent-based system built with the Strands framework that:
   - Explores repository structure using directory traversal tools
   - Reads relevant source files to understand project purpose and functionality
   - Uses AWS Bedrock inference profiles to generate documentation via Claude Sonnet 4.5
   - Writes the generated README.md to the project root
   - Supports interactive chat mode for iterative refinement

2. **Terraform Infrastructure**: Provisions AWS resources required for the application:
   - Creates a Bedrock inference profile pointing to Claude Sonnet 4.5 model
   - Manages AWS tagging and state through S3 backend
   - Enables cost tracking through cost allocation tags

**Key Interactions**:
- The CLI application authenticates with AWS using boto3
- Retrieves the inference profile ARN from Bedrock service
- Sends analysis prompts to the Claude model via the inference profile
- The AI agent uses custom tools (file reading, directory traversal) with path validation to analyze the target repository
- Generates structured README content based on a predefined template and system prompt

## III. Prerequisites

- **Python**: 3.13 or higher
- **Poetry**: For Python dependency management
- **AWS Account**: With appropriate permissions for:
  - AWS Bedrock service access
  - IAM role assumption (if using cross-account deployment)
  - S3 bucket access (for Terraform state)
  - DynamoDB table access (for Terraform state locking)
- **Terraform**: For infrastructure deployment (backend configured for `eu-west-1`)
- **AWS CLI**: Configured with valid credentials

## IV. Installation / Setup

### Application Setup

1. Navigate to the code directory:
```bash
cd code
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. The installation creates a CLI command `readme_generator` that can be invoked after activation.

### Infrastructure Setup

1. Navigate to the infrastructure directory:
```bash
cd iac
```

2. Set required variables in `terraform.tfvars`:
```hcl
project_name       = "your_project_name"
git_repository     = "your_git_repo_url"
role_to_assume_arn = "arn:aws:iam::ACCOUNT:role/ROLE_NAME"  # Optional
```

3. Initialize Terraform:
```bash
terraform init
```

4. Deploy the infrastructure:
```bash
terraform apply
```

This creates a Bedrock inference profile named `{project_name}_readme_generator`.

**Note**: If `role_to_assume_arn` is not provided (or set to empty string), Terraform will use the default AWS credentials configured in your environment.

## V. Usage

### Basic Usage

Generate a README for the current directory:

```bash
poetry run readme_generator -p <project_name>
```

Generate a README for a specific project path:

```bash
poetry run readme_generator -p <project_name> -r /path/to/project
```

### Interactive Chat Mode

Use chat mode to refine the generated README iteratively:

```bash
poetry run readme_generator -p <project_name> -c
```

In chat mode:
- The tool generates an initial README
- You can provide feedback to improve or modify sections
- Type `exit` when satisfied with the result

### Command-Line Options

- `-p, --project-name` (required): Project name used to identify the Bedrock inference profile
- `-r, --root-path` (optional): Root path of the project to document (defaults to current working directory)
- `-c, --chat-mode` (optional): Enable interactive mode for README refinement

### Example

```bash
# Generate README for a project in the current directory
poetry run readme_generator -p my_app

# Generate README for a specific path with chat mode
poetry run readme_generator -p my_app -r ~/projects/my_app -c
```

## VI. Infrastructure

### Terraform Resources

The infrastructure is managed through Terraform and provisions:

**`bedrock_inference_profile.tf`**:
- `aws_bedrock_inference_profile.main`: Creates an application-level inference profile
  - Model: Claude Sonnet 4.5 (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`)
  - Name: `{project_name}_{domain_name}`
  - Region-specific ARN construction
  - **Cost Allocation**: The inference profile enables cost allocation tags to track LLM call costs. The `domain_name` value is used as a tag, allowing you to monitor and attribute Bedrock API costs per domain in AWS Cost Explorer.

**Backend Configuration**:
- S3 bucket: `poc-terraform-backend-049810646332`
- DynamoDB table: `poc_terraform_backend`
- State file: `readme_generator.tfstate`
- Region: `eu-west-1`
- Encryption enabled

### Deployment Workflow

1. Ensure AWS credentials are configured
2. Update `terraform.tfvars` with project-specific values
3. Run `terraform init` to initialize providers and backend
4. Run `terraform plan` to preview changes
5. Run `terraform apply` to create resources
6. The inference profile ARN will be discoverable via the Bedrock API

### Authentication Options

The Terraform provider supports two authentication modes:

- **Role Assumption**: If `role_to_assume_arn` is provided, Terraform will assume the specified IAM role for deployment
- **Default Credentials**: If `role_to_assume_arn` is not provided or set to empty string, Terraform uses the default AWS credentials from your environment

### Cost Tracking

The Bedrock inference profile is tagged with the following cost allocation tags (defined in `terraform.tf`):
- `Appli`: The project name
- `Component`: The domain name (used for cost attribution)

These tags allow you to track and analyze LLM API costs in AWS Cost Explorer by filtering on the `Component` tag value (domain_name). This enables granular cost visibility per domain or application component.

### Assumptions

- The AWS account has access to Claude Sonnet 4.5 model in the specified region
- The S3 backend bucket and DynamoDB table already exist
- IAM permissions allow creating Bedrock inference profiles
- Cost allocation tags are enabled in AWS Billing and Cost Management

## VII. Configuration

### Application Configuration

Configuration is provided via command-line arguments:

- `project_name`: Used to construct the inference profile name as `{project_name}_readme_generator`
- `root_path`: Directory path the agent is allowed to access (enforced by path validation)

### Terraform Configuration

**Variables**:
- `project_name` (required): Name of the project
- `domain_name` (required): Name of the domain (typically "readme_generator") - used as a cost allocation tag
- `git_repository` (required): Git repository URL for resource tagging
- `role_to_assume_arn` (optional): ARN of the IAM role to assume for deployment
  - Default: `""` (empty string)
  - When empty, uses default AWS credentials configured in the environment

### System Prompt

The AI behavior is controlled by `system_prompt.txt`, which defines:
- The agent's role as a senior software engineer and technical writer
- Analysis guidelines (what to look for in repositories)
- README structure requirements
- Output behavior and constraints
- Feedback loop handling for chat mode

### README Template

The output format follows `readme_example.md`, ensuring consistent structure with sections:
- Project Overview
- Architecture/Design
- Prerequisites
- Installation/Setup
- Usage
- Infrastructure (if present)
- Configuration
- Project Structure
- Limitations/Assumptions

### Security Features

- **Path Validation**: The `check_root_path()` function prevents the agent from accessing files outside the specified root path
- **File Access**: Only read operations are allowed on the target project; write operations are restricted to README.md at the root

## VIII. Project Structure

### A. Application Code

**`code/readme_generator/`**
- `main.py`: Core application logic
  - `get_tree()`: Tool for exploring directory structure with recursive traversal
  - `read_file_as_string()`: Tool for reading file contents with path validation
  - `write_readme_file()`: Tool for writing the generated README
  - `get_inference_profile_arn()`: Retrieves the Bedrock inference profile by name
  - `main()`: Orchestrates the agent workflow and chat loop
  - `command_line_main()`: Click-based CLI entry point

- `system_prompt.txt`: System prompt defining agent behavior and analysis guidelines
- `readme_example.md`: Template structure for generated READMEs

**`code/pyproject.toml`**
- Poetry configuration file defining:
  - Project metadata (name: `readme_generator`, version: `0.2.0`)
  - Python dependencies: boto3, click, strands-agents (v1.9.0), strands-agents-tools (v0.2.8), strands-agents-builder (v0.1.10)
  - CLI script entry point (`readme_generator`)

### B. Infrastructure as Code

**`iac/`**
- `terraform.tf`: Provider configuration with default tags (Appli, Component, git_repository), S3 backend setup, and required providers
- `bedrock_inference_profile.tf`: Bedrock inference profile resource definition
- `variables.tf`: Input variables (project_name, domain_name, git_repository, role_to_assume_arn)
- `locals.tf`: Local values computed from variables (environment_name)
- `data.tf`: Data sources for AWS account ID and region
- `terraform.tfvars`: Variable values (gitignored for security)

## IX. Limitations / Assumptions

### Application Limitations

- **Region-Specific**: The Bedrock inference profile must be created in the same region where the application runs
- **Model Availability**: Assumes Claude Sonnet 4.5 model is available and accessible in the AWS account
- **Single README Output**: Only generates a README.md file at the project root (does not generate documentation for subdirectories)
- **Path Constraints**: The agent can only analyze files within the specified root path
- **No Offline Mode**: Requires active AWS credentials and internet connectivity
- **Session Storage**: Uses file-based session management with UUID-based session IDs stored locally

### Infrastructure Assumptions

- **Pre-existing Backend**: Assumes S3 bucket `poc-terraform-backend-049810646332` and DynamoDB table `poc_terraform_backend` already exist in `eu-west-1`
- **IAM Permissions**: The executing role/user must have permissions to:
  - Create and manage Bedrock inference profiles
  - List inference profiles
  - Assume the role specified in `role_to_assume_arn` (if provided)
- **Default Credentials Fallback**: When `role_to_assume_arn` is not provided, the system uses default AWS credentials from the environment
- **Bedrock Model Access**: The AWS account must have been granted access to Claude Sonnet 4.5 model through the Bedrock console
- **Cost Allocation Tags**: Assumes cost allocation tags are activated in AWS Billing and Cost Management console for cost tracking functionality

### Design Assumptions

- **Repository Structure**: Assumes standard repository layouts (e.g., presence of `pyproject.toml`, `requirements.txt`, `*.tf` files indicates purpose)
- **Text-Based Files**: The tool is optimized for text-based source code and configuration files
- **Token Budget**: Generated READMEs are constrained by the model's context window and output limits
- **Tool Integration**: Uses Strands framework for agent orchestration with custom tools (file_read, get_tree, write_readme_file)
