#!/bin/bash

# this script used for automation while building standalone binary from the Proxy.py

if ! [ -x "$(command -v python3)" ]; then
  echo '[!] Error: python 3 is not installed.'
  echo '[+] Please install with: sudo apt install python3'
  exit 1
fi

if ! [ -x "$(command -v pip3)" ]; then
  echo '[!] Error: python 3 is not installed.'
  echo '[+] Please install with: sudo apt install python3-pip'
  exit 1
fi

if ! [ -x "$(command -v cython)" ]; then
  echo '[!] Error: cython is not installed.'
  echo '[+] Please install with: pip3 install cython'
  exit 1
fi

echo '[+] Building with cython...'

cython --embed ./Proxy.py

echo '[+] Done!'

echo '[+] Compiling with GCC...'

PYTHON_VERSION__=$(python3 -V | awk '{ print $2 }' | awk -F\. '{ print $1"."$2 }')

gcc -Os -I /usr/include/python$PYTHON_VERSION__/ -o socks5proxy Proxy.c -l python$PYTHON_VERSION__ -l pthread -l m -l util -l dl -s

echo '[+] Done!'