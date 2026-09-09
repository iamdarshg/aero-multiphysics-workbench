terraform {
  required_version = ">= 1.7.0"
  required_providers { google = { source = "hashicorp/google", version = "~> 6.0" } }
}

variable "enable_remote_compute" { type = bool; default = false }
variable "project_id" { type = string; default = null }
variable "region" { type = string; default = "us-central1" }
variable "monthly_cost_ceiling_usd" { type = number; default = 0 }

# No remote resource exists unless a user explicitly enables this plan and supplies a project.
provider "google" { project = var.project_id, region = var.region }
resource "google_storage_bucket" "solver_artifacts" {
  count = var.enable_remote_compute ? 1 : 0
  name = "${var.project_id}-aero-solver-artifacts"
  location = var.region
  uniform_bucket_level_access = true
  lifecycle_rule { condition { age = 30 } action { type = "Delete" } }
}
output "remote_compute_enabled" { value = var.enable_remote_compute }
output "monthly_cost_ceiling_usd" { value = var.monthly_cost_ceiling_usd }
