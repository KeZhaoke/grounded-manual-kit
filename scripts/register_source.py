#!/usr/bin/env python3
from grounded_manual import main

raise SystemExit(main(["register-source", *(__import__("sys").argv[1:])]))

