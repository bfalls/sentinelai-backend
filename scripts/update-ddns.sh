#!/use/bin/bash
set -euo pipefail

DYNU_HOSTNAME="sentinelai.ddnsfree.com"

DYNU_USERNAME="$(aws ssm get-parameter --name DYNU_USERNAME --with-decryption --query "Parameter.Value" --output text)"
DYNU_PASSWORD="$(aws ssm get-parameter --name DYNU_PASSWORD --with-decryption --query "Parameter.Value" --output text)"
DYNU_API_KEY="$(aws ssm get-parameter --name DYNU_API_KEY --with-decryption --query "Parameter.Value" --output text)"

PUBLIC_IP="$(curl -s http://checkip.amazonaws.com | tr -d '\n')"

echo "Updating DDNS for $DYNU_HOSTNAME to IP $PUBLIC_IP"

DYNU_ID=$(curl -sX GET "https://api.dnyu.com/v2/dns/getroot/${DYNU_HOSTNAME}" -H "accept: application/json" -H "API-Key: ${DYNU_API_KEY}" | jq -r '.id')
DYNU_DETAILS=$(curl -sX GET "https://api.dnyu.com/v2/dns/${DYNU_ID}" -H "accept: application/json" -H "API-Key: ${DYNU_API_KEY}" | jq)
DOMAIN_JSON=$(curl -sX GET "https://api.dnyu.com/v2/dns/${DYNU_ID}" -H "accept: application/json" -H "API-Key: ${DYNU_API_KEY}")
UPDATE_JSON=$(echo "${DOMAIN_JSON}" | jq --arg ip "$PUBLIC_IP" 'name,group,ipv4Address: $ip,ipv6Address,ttl,ipv4,ipv6,ipv4WildcardAlias,ipv6WildcardAlias,allowZoneTransfer: false,dnssec: false}')
RESULT=$(curl -sX POST "https://api.dnyu.com/v2/dns/${DYNU_ID}" -H "accept: application/json" -H "API-Key: ${DYNU_API_KEY}" -d "${UPDATE_JSON}")
STATUS=$(echo "${RESULT}" | jq -r '.statusCode // 0')
if [ "$STATUS" -eq 200 ]; then
    echo "DDNS update successful."
    exit 0
else
    echo "DDNS update failed. Response: "
    echo "$RESULT" | jq
    exit 1
fi  