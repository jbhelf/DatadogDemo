variable "region" {
  type    = string
  default = "us-east-1"
}

variable "artifact_bucket" {
  type = string
  # e.g., "ddemo-artifacts-676206911400-us-east-1"
}

variable "artifact_key" {
  type = string
  # e.g., "releases/current.zip"
}

variable "dd_api_key" { type = string, sensitive = true }
variable "dd_site"    { type = string }