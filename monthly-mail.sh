#!/bin/bash

source $HOME/.profile

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"
current_datetime=$(date +"%Y-%m-%d_%H-%M-%S")
log_filename="log_${current_datetime}.log"

docker build --tag spot-pricing:execute -f .devcontainer/Dockerfile .
docker run --rm \
    --mount type=bind,src=./src,dst=/src \
    --workdir /src \
    -e ZAPTEC_USERNAME="${ZAPTEC_USERNAME}" \
    -e ZAPTEC_PASSWORD="${ZAPTEC_PASSWORD}" \
    -e ENTSOE_API_TOKEN="${ENTSOE_API_TOKEN}" \
    -e SMTP_PASSWORD="${SMTP_PASSWORD}" \
    spot-pricing:execute /usr/local/bin/python mailer.py > $log_filename
