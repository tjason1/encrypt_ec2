# encrypt_ec2
Finds unencrypted volumes associated with an ec2 instance, takes snapshots, creates new encrypted volumes, and switches the volumes on the instance out.

Utilizes pipenv and the aws cli, please install.

Run with **pipenv run python decrypt.py** *<aws_cli_profile_name>*
if using default aws cli profile, no profile name argument is necessary

You will be prompted for the instance ID 
