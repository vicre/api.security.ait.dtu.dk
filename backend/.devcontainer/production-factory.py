#!/usr/bin/env python3
import yaml

# The command to be added to the xx-api-security-ait-dtu-dk-app-main service
COMMAND = '"bash -c \\"cd /usr/src/project/app-main && source /usr/src/venvs/app-main/bin/activate && gunicorn app.wsgi:application --bind 0.0.0.0:8121\\""'

# The path to the development docker-compose file
DEVELOPMENT_FILE = "./my-development-docker-compose.yaml"
# The path to the production docker-compose file
PRODUCTION_FILE = "./my-production-docker-compose.yaml"

with open(DEVELOPMENT_FILE, 'r') as dev_file:
    # Load the YAML content
    content = yaml.safe_load(dev_file)

    # Modify or add the command in the xx-api-security-ait-dtu-dk-app-main service
    content['services']['xx-api-security-ait-dtu-dk-app-main']['command'] = COMMAND

with open(PRODUCTION_FILE, 'w') as prod_file:
    # Write the modified content back to a new file
    yaml.safe_dump(content, prod_file, default_flow_style=False, sort_keys=False)

print("Production docker-compose file has been created.")