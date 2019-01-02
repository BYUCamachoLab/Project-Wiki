#! /bin/bash

killall python PW_run.py
killall mongod
killall caddy -conf PW_Caddyfile
pkill "caddy"
echo "Project Wiki Stopped"