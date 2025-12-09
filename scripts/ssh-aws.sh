#!/usr/bin/env bash
set -euo pipefail

NAME_TAG="sentinelai"
REGION="us-east-1"
KEY_PATH="sentinelai.pem"
USER="ec2-user"

HOST=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:Name,Values=$NAME_TAG" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].PublicDnsName" \
  --output text)

if [ -z "$HOST" ] || [ "$HOST" = "None" ]; then
  echo "No running instance found with Name=$NAME_TAG in $REGION" >&2
  exit 1
fi

ssh -i "$KEY_PATH" "${USER}@${HOST}"
