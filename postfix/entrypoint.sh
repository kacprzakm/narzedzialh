#!/bin/bash
set -euo pipefail

sed \
    -e "s/POSTFIX_HOSTNAME_PLACEHOLDER/${POSTFIX_HOSTNAME:-mx.example.com}/g" \
    -e "s/MAIL_DOMAIN_PLACEHOLDER/${MAIL_DOMAIN:-test.example.com}/g" \
    /etc/postfix/main.cf.template > /etc/postfix/main.cf

postfix check

trap 'postfix stop; exit 0' SIGTERM SIGINT

exec postfix start-fg
