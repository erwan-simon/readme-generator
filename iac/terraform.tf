provider "aws" {
  default_tags {
    tags = {
      Appli          = var.project_name
      Component      = local.domain_name
      git_repository = var.git_repository
    }
  }
  assume_role {
    role_arn = var.role_to_assume_arn
  }
}

terraform {
  backend "s3" {
    key                  = "readme_generator.tfstate"
    workspace_key_prefix = ""
    encrypt              = true
    region               = "eu-west-1"
  }
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}
