# Lab job registry: intent

Intent: lab automation jobs (sample sweeps, label print runs, stability checks) are registered in one in-process registry so the scheduler can find them by key and by tag. Each job carries its namespace tag, its own tags only, and an optional timezone-aware expiry. Callbacks built per named step must each run their own step. Expired jobs are removed on the scheduler tick without interrupting the sweep, and the registry stays usable afterwards.
