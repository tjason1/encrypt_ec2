import boto3
import botocore

session = boto3.Session(profile_name='pa')
ec2 = session.resource('ec2')

def list_volumes(id):
    "List ec2 volumes for the entered instance, returns True if there is at least one unencrypted drive on the instance"

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
    print("Instance {0} has stopped\n".format(i.id))
    
    return

def start_instance(id):
    "Start EC2 instances"

    i = ec2.Instance(id)

    print("Starting {0}...".format(i.id))
    i.start()
    i.wait_until_running()
    print("Instance {0} is now running\n".format(i.id))

    return

def snapshot_ids(id):
    "Returns list of snapshots associated with an EC2 instance"

    i = ec2.Instance(id)
    snapshots = []

    for v in i.volumes.all():
        for s in v.snapshots.all():
            snapshots.append(s.id)

    return snapshots

def volume_ids(id):
    "Returns list of volumes associated with an EC2 instance"

    i = ec2.Instance(id)
    volumes = []

    for v in i.volumes.all():
        volumes.append(v.id)

    return volumes

def snap_unencrypted(id):
    "Take snapshots of unencrypted EC2 volumes and return list of the new snapshot ID's"

    i = ec2.Instance(id)
    starting_snaps = snapshot_ids(id)

    # Take snaps of all unencrypted drives
    for v in i.volumes.all():
        if (v.encrypted and "Encrypted" or "Not Encrypted") == "Not Encrypted":
            if has_pending_snapshot(v):
                print( "Skipping {0}, snapshot already in progress".format(i.id))
            print ("Creating snapshot of {0}".format(v.id))
            v.create_snapshot(Description="Created by volume encrypter")
        else:
            print('Skipping {0}, volume is already encrypted')

    ending_snaps = snapshot_ids(id)
    new_snaps = (list(set(ending_snaps) - set(starting_snaps)))

    # Wait for all snaps to complete
    for v in i.volumes.all():
        for s in v.snapshots.all():
            if s.id in new_snaps:
                print('Waiting for snapshot {0} to complete'.format(s.id))
                s.wait_until_completed()
                print('Snapshot {0} of volume {1} created'.format(s.id, v.id))

    print ("All snapshots Complete\n")

    return new_snaps

def has_pending_snapshot(volume):
    "Detects if there is a snapshot already in progress for a volume"

    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

def create_volumes(snapshots,id):
    "Create new encrypted volumes from list of snapshot ID's. Utilizes the default KMS managed EBS key. Returns a mapping of old volume IDs to new"

    i = ec2.Instance(id)
    ec2_client=boto3.client('ec2')
    waiter = ec2_client.get_waiter('volume_available')
    volume_pairs = {}

    # Create encrypted volumes from a list of snapshot ID's
    for v in i.volumes.all():
        for s in v.snapshots.all():
            if s.id in snapshots:
                # Detect is volume is an io1, which needs to have the iops specified
                if v.volume_type == 'io1':
                    print('Creating encrypted volume of {0} from snapshot {1}.'.format(v.id, s.id))
                    new_volume = ec2.create_volume(
                        AvailabilityZone = v.availability_zone,
                        Encrypted = True,
                        Iops = v.iops,
                        Size = v.size,
                        SnapshotId = s.id,
                        VolumeType = v.volume_type,
                        DryRun = False,
                        MultiAttachEnabled= v.multi_attach_enabled
                    )
                    volume_pairs.update( {v.id : new_volume.id})
                else:
                    print('Creating encrypted volume of {0} from snapshot {1}.'.format(v.id, s.id))
                    new_volume = ec2.create_volume(
                        AvailabilityZone = v.availability_zone,
                        Encrypted = True,
                        Size = v.size,
                        SnapshotId = s.id,
                        VolumeType = v.volume_type,
                        DryRun = False,
                        MultiAttachEnabled= v.multi_attach_enabled
                    )

                    print('New volume {0} created, waiting for it to become available'.format(new_volume.id))
                    waiter.wait(VolumeIds=[new_volume.volume_id])
                    print('New volume is now available')

                    volume_pairs.update( {v.id : new_volume.id})

    print('Creation of new encrypted volumes complete\n')
            
    return volume_pairs

def attach_new(id,volume_map):
    "Detaches a volume and replaces it with another using the same mount. Takes in a map of old volume id and replacement volume id."

    i = ec2.Instance(id)
    ec2_client=boto3.client('ec2')
    waiter = ec2_client.get_waiter('volume_available')

    for v in i.volumes.all():
        print ('Detaching unencrypted volume {0} from instance {1} and relacing with volume {2}'.format(v.id, id, (volume_map[v.id])))
        instance_device = (v.attachments[0]['Device'])
        v.detach_from_instance(
            Device = instance_device,
            Force = False,
            InstanceId = (id),
        )
        waiter.wait(VolumeIds=[v.volume_id])
        i.attach_volume(
            VolumeId = (volume_map[v.id]),
            Device = instance_device,
        )

    print ('All unencrypted volumes have now been replace with encrypted duplicates\n')

    return


### Main Program Logic ####
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
    go_ahead = input('Please enter yes if you wish to proceed - THIS INSTANCE WILL BE STOPPED: \n')
    if go_ahead == 'yes':
        print ('\n')
        stop_instance(id)
        new_snap_ids = snap_unencrypted(id)
        volume_ids = create_volumes(new_snap_ids,id)
        attach_new(id,volume_ids)
        start_instance(id)
        print ('''All unencypted volumes have now been encrypted. Please validate your instance.
The unencrypted volumes have NOT been deleted in the event a rollback is necessary.''')
    else:
        print('\nNot proceeding with the volume encryption process, have a great day!\n\n')
