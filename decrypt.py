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
            v.state,
            str(v.size) + "GiB",
            v.encrypted and "Encrypted" or "Not Encrypted"
        )))

        if (v.encrypted and "Encrypted" or "Not Encrypted") == "Not Encrypted":
            not_encrypted = True

    return not_encrypted

def stop_instance(id):
    "Stop EC2 instance"

    i = ec2.Instance(id)

    print("Stopping {0}...".format(i.id))
    i.stop()
    i.wait_until_stopped()
    print("Instance {0} has stopped".format(i.id))
    
    return

def snapshot_ids(id):

    i = ec2.Instance(id)
    snapshots = []

    for v in i.volumes.all():
        for s in v.snapshots.all():
            snapshots.append(s.id)

    return snapshots

def snap_unencrypted(id):
    "Take Snapshots of Unencrypted EC2 Volumes"

    i = ec2.Instance(id)
    starting_snaps = snapshot_ids(id)

    for v in i.volumes.all():
        if (v.encrypted and "Encrypted" or "Not Encrypted") == "Not Encrypted":
            if has_pending_snapshot(v):
                print( "Skipping {0}, snapshot already in progress".format(i.id))
            print ("Creating snapshot of {0}".format(v.id))
            v.create_snapshot(Description="Created by volume encrypter")
        else:
            print('Skipping {0}, volume is already encrypted')

    print ('Waiting for snapshots to complete')

    ending_snaps = snapshot_ids(id)
    new_snaps = (list(set(ending_snaps) - set(starting_snaps)))

    for snap in new_snaps:
        snap.wait_until_completed()

    print ("Snapshots Complete")

def has_pending_snapshot(volume):
    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

if __name__ == '__main__':
    id = input("Please enter the instance ID: ")
    print(''' 
Here is a list of the current volumes on this instance:
Includes Volume ID, status, size, and encryption state.\n''')
    unencrypted = list_volumes(id)
    if not unencrypted:
        print('Congrads all of your drives are encrypted!!!')
    else:
        print('''
You have one or more volumes that are not encrypted. Do you want to encrypt these volumes?\n
This will involve shutting down the instance, 
taking volume snapshots for all unencrypted volumes,
creating new encrypted volumes from the snapshots,
detaching the current volumes, 
attaching the new encrypted volumes,
and finally restarting the instance.
''')
    go_ahead = input('Please enter yes if you wish to proceed - THIS INSTANCE WILL BE STOPPED: ')
    if go_ahead == 'yes':
        stop_instance(id)
        snap_unencrypted(id)
    else:
        print('\nNot proceeding with the volume encryption process, have a great day!\n\n')
