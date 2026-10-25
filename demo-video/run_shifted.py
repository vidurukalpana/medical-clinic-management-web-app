# Runs the API with its clock moved to a weekday morning, for recording the demo only.
import os, time_machine, uvicorn
time_machine.travel(os.environ["DEMO_NOW"], tick=True).start()
uvicorn.run("main:app", host="0.0.0.0", port=8000)
