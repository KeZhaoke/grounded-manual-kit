#!/usr/bin/env python3
from grounded_manual import main

raise SystemExit(main(["verify-sources", *(__import__("sys").argv[1:])]))

