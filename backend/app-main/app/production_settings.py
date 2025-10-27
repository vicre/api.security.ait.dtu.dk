from .settings import *
from termcolor import colored
import getpass

current_user = getpass.getuser()  # Get the current user's login name
print(colored(f'Running as {current_user}', 'green'))