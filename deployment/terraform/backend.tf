terraform {
  backend "gcs" {
    bucket = "qwiklabs-gcp-04-ce9327734f37-terraform-state"
    prefix = "prod"
  }
}
