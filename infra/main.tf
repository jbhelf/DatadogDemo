terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

# Use default VPC/subnets to keep it simple
data "aws_vpc" "default" { default = true }

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Group: allow HTTP from anywhere, all egress
resource "aws_security_group" "web_sg" {
  name        = "ddemo-web-sg"
  description = "Allow HTTP"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "ddemo-web-sg" }
}

# IAM role for EC2 to read from S3 and use SSM
resource "aws_iam_role" "ec2_role" {
  name = "ddemo-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
}

# Instance permissions: S3 read to your artifact bucket + SSM basics
resource "aws_iam_policy" "ec2_policy" {
  name   = "ddemo-ec2-s3-ssm"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = ["s3:GetObject","s3:ListBucket"],
        Resource = [
          "arn:aws:s3:::${var.artifact_bucket}",
          "arn:aws:s3:::${var.artifact_bucket}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "ssm:DescribeAssociation",
          "ssm:GetDeployablePatchSnapshotForInstance",
          "ssm:GetDocument",
          "ssm:DescribeDocument",
          "ssm:GetManifest",
          "ssm:ListAssociations",
          "ssm:ListInstanceAssociations",
          "ssm:PutInventory",
          "ssm:PutComplianceItems",
          "ssm:PutConfigurePackageResult",
          "ssm:UpdateAssociationStatus",
          "ssm:UpdateInstanceAssociationStatus",
          "ssm:UpdateInstanceInformation",
          "ssmmessages:*",
          "ec2messages:*"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.ec2_policy.arn
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "ddemo-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# Latest Amazon Linux 2023 (x86_64)
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["137112412989"] # Amazon

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  app_dir = "/opt/urlshort"
}

# EC2 instance
resource "aws_instance" "web" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t2.micro"
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.web_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail

    dnf update -y
    dnf install -y python3 unzip awscli

    mkdir -p ${local.app_dir}
    python3 -m venv ${local.app_dir}/venv

    # Write deploy script that pulls artifact from S3 and (re)starts the service
    cat >/usr/local/bin/deploy.sh <<'DEPLOY'
    #!/bin/bash
    set -euo pipefail
    ARTIFACT_S3="$1"   # e.g., s3://BUCKET/releases/current.zip
    APP_ROOT="${local.app_dir}"
    APP_DIR="${local.app_dir}/app"

    mkdir -p "$APP_ROOT"
    cd "$APP_ROOT"

    # Fetch artifact from S3
    aws s3 cp "$ARTIFACT_S3" app.zip --quiet
    rm -rf app || true
    mkdir app
    unzip -q app.zip -d app

    # Install dependencies
    source ${local.app_dir}/venv/bin/activate
    pip install -r app/requirements.txt --quiet

    # Create/Update systemd service to serve Flask on :80
    cat >/etc/systemd/system/urlshort.service <<SERVICE
    [Unit]
    Description=URL Shortener Flask App
    After=network.target

    [Service]
    WorkingDirectory=${local.app_dir}
    Environment=DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    ExecStart=${local.app_dir}/venv/bin/python -m flask --app app/app.py run --host 0.0.0.0 --port 80
    Restart=on-failure
    User=root

    [Install]
    WantedBy=multi-user.target
    SERVICE

    systemctl daemon-reload
    systemctl enable --now urlshort.service
    DEPLOY
    chmod +x /usr/local/bin/deploy.sh

    # Ensure SSM agent is running (AL2023 has it by default)
    systemctl enable --now amazon-ssm-agent
  EOF

  tags = {
    Name         = "ddemo-web"
    app          = "urlshort"
    environment  = "demo"
    cost_center  = "ddemo"
  }
}