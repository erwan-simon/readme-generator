resource "aws_bedrock_inference_profile" "main" {
  name        = local.environment_name
  description = "Bedrock inference profile for ${local.environment_name}"

  model_source {
    copy_from = "arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:inference-profile/global.anthropic.claude-sonnet-4-5-20250929-v1:0"
  }
}
