#!/bin/bash
# Start Cloudflare Tunnel to expose the local FastAPI server
# Prerequisites: Install cloudflared from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
#
# First-time setup:
#   cloudflared tunnel login
#   cloudflared tunnel create grailseeker
#   cloudflared tunnel route dns grailseeker <your-subdomain>.cfargotunnel.com
#
# Quick start (no account needed):
#   cloudflared tunnel --url http://localhost:8000

echo "Starting Cloudflare Tunnel → http://localhost:8000"
cloudflared tunnel --url http://localhost:8000
