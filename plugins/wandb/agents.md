## Weights & Biases — track training and evaluations

Use Weights & Biases for every model-training or evaluation run unless the
user explicitly opts out. The shell provides authentication through
`WANDB_API_KEY`; never copy, print, log, or commit the credential itself.

- Keep W&B in online mode so results are updated while a run is active; do
  not silently switch to offline or disabled mode.
- Use descriptive project, group, and run names, and log the configuration,
  random seed, model and dataset identifiers, git commit, metrics, and output
  artifacts needed to reproduce the run. `tools/wandb_init.py` in each
  project does this.
- Integrate W&B into new training/evaluation scripts before starting long
  runs. Resume interrupted runs when practical and finish each run cleanly so
  its final state and results are visible in W&B.
