#!/bin/bash
curl -Lo upcloud-cli_3.36.0_amd64.deb https://github.com/UpCloudLtd/upcloud-cli/releases/download/v3.36.0/upcloud-cli_3.36.0_amd64.deb
# Preferably verify the asset before proceeding with install, see "Verify assets" below
sudo apt install ./upcloud-cli_3.36.0_amd64.deb
sudo apt install bash-completion
