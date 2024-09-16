import os

from samples.entrypoint import uc
# you need to import the functions you want to register
from my_functions import *


# set databricks host and token
# os.environ["DATABRICKS_HOST"] = host
# os.environ["DATABRICKS_TOKEN"] = token





if __name__ == "__main__":
    # make sure you add the secret for redact_with_secret for the scope and key
    uc.deploy()
