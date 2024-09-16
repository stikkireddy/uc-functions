from pathlib import Path

from uc_functions import FunctionDeployment

root_dir = str(Path(__file__).parent)
uc = FunctionDeployment("main",
                        "default",
                        root_dir,
                        globals_dict=globals())