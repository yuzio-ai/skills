# Fixture rules
Use Python standard library only. This is a temporary live behavioral fixture.
Controller prepares fixture and Cadra artifacts only. Workers own named implementation files. Reviewers and validate may read business files and run named unit tests; only implementation stages may modify business/test files.
No install, network, commit or push. No formal project docs needed for these tiny changes; Cohestra handoffs suffice. Respect each task's file ownership.
Validation commands use `python3 -B -m unittest <test module> -v`. All current files are untracked fixture baseline: snapshots and exact diffs are required, not Git HEAD.
