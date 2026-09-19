terraform {
  required_version = ">= 1.7.0"
  required_providers { google = { source = "hashicorp/google", version = "~> 6.0" } }
}

# --- user-owned remote authorization (fail closed by default) ---------------
variable "enable_remote_compute" { type = bool; default = false }
variable "project_id" { type = string; default = null }
variable "region" { type = string; default = "us-central1" }
variable "monthly_cost_ceiling_usd" { type = number; default = 0 }

# Immutable remote execution limits. An AI/tool call can never set these; only
# the interactive operator supplies them via a reviewed plan. The runner
# mirrors these limits in participants/remote_policy.py.
variable "worker_image_digest" { type = string; default = "" }
variable "max_vcpu" { type = number; default = 2 }
variable "max_memory_mib" { type = number; default = 4096 }
variable "max_concurrency" { type = number; default = 1 }
variable "max_wall_time_s" { type = number; default = 1800 }
variable "max_job_cost_usd" { type = number; default = 0.15 }
variable "max_session_cost_usd" { type = number; default = 0.49 }

locals {
  remote_enabled         = var.enable_remote_compute && var.project_id != null && var.project_id != ""
  worker_image_pinned    = var.worker_image_digest != ""
  # No worker image may run until a digest is explicitly pinned.
  remote_execution_ready = local.remote_enabled && local.worker_image_pinned
}

# No remote resource exists unless a user explicitly enables this plan, supplies
# a project, and pins a worker image digest.
provider "google" { project = var.project_id, region = var.region }

resource "google_storage_bucket" "solver_artifacts" {
  count = local.remote_enabled ? 1 : 0
  name = "${var.project_id}-aero-solver-artifacts"
  location = var.region
  uniform_bucket_level_access = true
  lifecycle_rule { condition { age = 30 } action { type = "Delete" } }
}

# Pinned worker image registry (INFRA-FIX 02). The digest consumed by the
# executor is referenced here; it is never supplied by an AI/tool call.
resource "google_artifact_registry_repository" "solver_workers" {
  count         = local.remote_enabled ? 1 : 0
  location      = var.region
  repository_id = "aero-solver-workers"
  description   = "Pinned governed native worker images (digest-addressed)."
  format        = "DOCKER"
}

resource "google_service_account" "solver_runner" {
  count        = local.remote_enabled ? 1 : 0
  account_id   = "aero-solver-runner"
  display_name = "Governed remote solver runner"
}

output "remote_compute_enabled" { value = var.enable_remote_compute }
output "remote_execution_ready" { value = local.remote_execution_ready }
output "worker_image_digest" { value = var.worker_image_digest }
output "monthly_cost_ceiling_usd" { value = var.monthly_cost_ceiling_usd }
output "max_vcpu" { value = var.max_vcpu }
output "max_memory_mib" { value = var.max_memory_mib }
output "max_concurrency" { value = var.max_concurrency }
output "max_wall_time_s" { value = var.max_wall_time_s }
output "max_job_cost_usd" { value = var.max_job_cost_usd }
output "max_session_cost_usd" { value = var.max_session_cost_usd }
