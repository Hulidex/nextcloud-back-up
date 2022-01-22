#!/usr/bin/env python3

# Author: Jolu Izquierdo alias Hulidex
# Description: Make a back-up of Nextcloud environment, the script is based on
# Nextcloud's official documentation:
# https://docs.nextcloud.com/server/18/admin_manual/maintenance/backup.html
# If you want to restore a back up you can also check official Nextcloud
# documentation:
# https://docs.nextcloud.com/server/18/admin_manual/maintenance/backup.html
# Python Version: >= 3.7


import os
import sys
import pathlib
import json
from subprocess import Popen, PIPE
from datetime import datetime


###############################################################################
#                                  FUNCTIONS                                  #
###############################################################################


def is_user_root():
    """ Check is the script is running with root permissions
    """
    return (True if os.getuid() == 0 else False)


def abort(message, *, cause):
    """ Abort script with an error message

    :param str message: The error message
    :param str cause: Cause of the error
    """
    # If it's a byte-like object decode it
    try:
        message = message.decode()
    except (UnicodeDecodeError, AttributeError):
        pass
    print(f'Error:{cause}\n{message}', file=sys.stderr)
    sys.exit(1)


def check_file_exists(path):
    pass


def check_packages(packages):
    pass


def send_mail(body):
    pass


def nextcloud_rescue_mode(*, enable=True):
    """Set Nextcloud rescue mode

    :param bool enable: 'True' enables rescue mode, 'False' disables it
    """
    nextcloud_config_file = f'{NEXTCLOUD_ROOT_FOLDER}/config/config.php'
    nextcloud_back_up_file = nextcloud_config_file + '.old'

    with open(nextcloud_config_file, 'r') as f:  # Open for read
        lines = f.readlines()  # Read file into memory

        # Back up the file in case the rest operations go wrong
        with open(nextcloud_back_up_file, 'w') as recovery:
            recovery.writelines(lines)

        for index, line in enumerate(lines):
            # Look for the file's line with property 'maintenance'
            if line.find('maintenance') != -1:
                if enable:
                    text, replace = 'false', 'true'
                else:
                    text, replace = 'true', 'false'

                lines[index] = line.replace(text, replace)  # Change property
                break  # Exit loop

    with open(nextcloud_config_file, 'w') as f:  # Open for write
        f.writelines(lines)  # Write from memory into the file

    if f.closed:  # Remove back up file if everything run successfully
        os.remove(nextcloud_back_up_file)


def run_cmd(command):
    """Run System command

    :param list command: Command to run

    :return A two elements, the first is the output of the command if no error
    was produced and the second the output of the command if a error is
    produced.
    :rtype string

    """
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()

    return out, err


def key_exists(key, dictionary):
    """Check if a key exists and is diferent from 'None'

    :param string key: key to look for
    :param dict dictionary: dictionary
    """
    return key in dictionary and dictionary[key] is not None


def device_mounted(uuid):
    """Check if a device is mounted in the system

    :param string uuid: Device's uuid
    :return The mount point if the device is found and None otherwise
    :rtype string
    """
    out, err = run_cmd(['lsblk', '-o', 'NAME,UUID,MOUNTPOINT', '--json'])

    blockdevices = json.loads(out)['blockdevices']

    for blkdevice in blockdevices:
        if key_exists('children', blkdevice):
            for child in blkdevice['children']:
                if key_exists('mountpoint', child) and child['uuid'] == uuid:
                    return child['mountpoint']


def mount_device(uuid):
    """Mount a device in the system

    :param str uuid: Device's uuid
    :return The mount point if the device is mounted and None otherwise
    :rtype string
    """
    mount_point = f'/mnt/{uuid}/back-up'
    # Create mountpoint if it doesn't exist
    pathlib.Path(mount_point).mkdir(parents=True, exist_ok=True)

    # Mount device
    out, err = run_cmd(['mount', '--uuid', uuid, mount_point])

    if not err:
        return mount_point
    else:
        abort(err, cause='mount')


def unmount_device(mount_point):
    """Unmount a device

    :param str mount_point: Device's mount point
    """
    out, err = run_cmd(['umount', mount_point])

    if err:
        abort(err, cause='umount')


def check_fs(uuid):
    """Check the file system of a blockdevice

    :param str uuid: Device's uuid
    :return The file system type (vfat, ext4, swap...) or None if the device
    with the given uuid is not found or it haven't a file system because the
    uuid doesn't belong to a partition
    :rtype string
    """
    out, err = run_cmd(['lsblk', '-o', 'UUID,FSTYPE', '--json'])

    blockdevices = json.loads(out)['blockdevices']

    for blkdevice in blockdevices:
        if key_exists('uuid', blkdevice) and blkdevice['uuid'] == uuid:
            return blkdevice['fstype']


###############################################################################
#                                    CONFIG                                   #
###############################################################################

# ABSOLUTE PATH to Nextcloud ROOT folder
# WARNING DO NOT ADD '/' AT THE END OF THE PATH
# valid path: '/foo/bar'
# invalid path: '/foo/bar/'
NEXTCLOUD_ROOT_FOLDER = ''

# UUID Device's partition you will use for back up, you can guess it by typing
# the following command as root user:
# $ blkid /dev/sdXY
# Where 'X' is the block device letter and 'Y' the partition number
# Example:
# $ blkid /dev/sda1
PART_UUID = ''

# Unmount back up device once everything is done.
UNMOUNT_DEVICE = True

# Maximum number of back ups in the device
# PENDING
MAX_COPIES = 10

# You can guess the values of the followings variables in the Nextcloud config
# file: NEXTCLOUD_ROOT_FILE/config/config.php

# Database type, it can be one of the followings:
# postgresql, mysql, sqlite, mariadb
DATABASE = ''

# Database user name
DATABASE_USER = ''

# Nextcloud database name
DATABASE_NAME = ''

# Database password
DATABASE_PASSWD = ''

# Database host
DATABASE_HOST = 'localhost'

# Database port
DATABASE_PORT = '5432'

###############################################################################
#                                     MAIN                                    #
###############################################################################


if __name__ == '__main__':
    if not is_user_root():  # Abort if the user isn't root
        abort("The script hasn't root permissions",
              cause='Improper permissions')

    if check_fs(PART_UUID) != 'ext4':  # Check ext4 FS
        message = """If the back up device isn't formatted with an ext4 file system rsync can't
        keep the permissions of the files it's trying to copy and errors will
        eventually occurs"""
        abort(message,
              cause=f"Invalid File system or Device {PART_UUID} doesn't found")

    # Mount device
    mount_point = device_mounted(PART_UUID)
    if mount_point is None:  # Check if the device is not mounted
        mount_point = mount_device(PART_UUID)  # Mount device

    # Create back up folders
    backup_folder = f"{mount_point}/{datetime.now().strftime('%Y/%m/%d/%H%M')}"
    backup_folder = backup_folder.replace('//', '/')  # Avoid bad typed paths
    pathlib.Path(backup_folder).mkdir(parents=True, exist_ok=True)

    nextcloud_rescue_mode(enable=True)  # Enable Nextcloud rescue mode

    # Back up Nextcloud main folders
    for important_folder in ['config', 'themes', 'data']:
        command = ['rsync', '-Aarqx',
                   f'{NEXTCLOUD_ROOT_FOLDER}/{important_folder}',
                   backup_folder]

        out, err = run_cmd(command)
        if err:
            nextcloud_rescue_mode(enable=False)
            abort(err, cause='rsync')
    # Back up database
    if DATABASE == 'postgresql':
        os.environ['PGPASSWORD'] = DATABASE_PASSWD
        command = ['pg_dump', DATABASE_NAME, '-U', DATABASE_USER, '-f',
           f'{backup_folder}/nextcloud_db.bak', '-h', DATABASE_HOST,
           '-p', DATABASE_PORT]
        out, err = run_cmd(command)
        if err:
            nextcloud_rescue_mode(enable=False)
            abort(err, cause='pg_dump')
    elif DATABASE == 'mysql' or DATABASE == 'mariadb':
        print('Pending')
    elif DATABASE == 'sqlite':
        print('Pending')

    # Back up certificates
    nextcloud_rescue_mode(enable=False)  # Disable Nextcloud rescue mode

    if UNMOUNT_DEVICE:
        unmount_device(mount_point)
