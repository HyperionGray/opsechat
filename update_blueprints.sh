#!/bin/bash
# Script to update blueprint files with current_app references

# Update email_routes.py
sed -i 's/app\.config\[/current_app.config[/g' /workspace/email_routes.py

# Update burner_routes.py  
sed -i 's/app\.config\[/current_app.config[/g' /workspace/burner_routes.py

# Update security_routes.py
sed -i 's/app\.config\[/current_app.config[/g' /workspace/security_routes.py

echo "Updated blueprint files with current_app references"