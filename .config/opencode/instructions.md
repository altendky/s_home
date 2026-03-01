# Temporary Files

Use `/tmp/agents/<uuid>/` as your temporary directory. Generate a UUID using `python3 -c "import uuid; print(uuid.uuid4())"` or `uuidgen` and create this directory on first need, then reuse the same path for the remainder of the session. This path has pre-approved allow permissions so no permission prompts are needed.
