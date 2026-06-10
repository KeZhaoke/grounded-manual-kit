#!/usr/bin/env python3
from grounded_manual import main

raise SystemExit(main(["audit-claims", *(__import__("sys").argv[1:])]))

