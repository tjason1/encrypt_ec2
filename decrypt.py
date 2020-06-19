import boto3
import botocore

session = boto3.Session(profile_name='pa')
ec2 = session.resource('ec2')

def list_volumes(id):
    "List ec2 volumes for the entered instance"

    i = ec2.Instance(id)
    not_encrypted = False

    for v in i.volumes.all():
        print(", ".join((
            v.id,
            i.id,
            v.state,
            str(v.size) + "GiB",
            v.encrypted and "Encrypted" or "Not Encrypted"
        )))
        if (v.encrypted and "Encrypted" or "Not Encrypted") == "Not Encrypted":
            not_encrypted = True

    if not_encrypted:
        print('You have a volume that is not encrypted')
    else:
        print('You have no encrypted drives')

    return not_encrypted

id = input("Please enter the instance ID: ")
has_encrypted_drives = list_volumes(id)
print(has_encrypted_drives)
