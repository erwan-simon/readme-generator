variable "project_name" {
  type        = string
  description = "Name of the project"
}

variable "git_repository" {
  type        = string
  description = "git respository from which this resource is from"
}

variable "role_to_assume_arn" {
  type        = string
  description = "ARN of the role to assume to deploy the resources"
  default     = ""
}
