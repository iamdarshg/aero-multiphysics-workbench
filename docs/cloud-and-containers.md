# Containers and cloud boundary

The local Docker and Terraform files are reviewable manifests, not deployment evidence. There are no image digests, pushed images, Terraform state, provisioned resources, cloud URLs, or billing receipts in this worktree.

For a future controlled deployment: review pinned base-image policy, build and scan an image, record its digest, configure an isolated GCP project and retention policy, establish a hard user-approved cost envelope/budget alerts, run and retain `terraform plan`, explicitly set `enable_remote_compute=true`, apply with an authenticated operator, then record actual resource identifiers and job/result provenance. Keep remote authorization separate from local capability readiness.
