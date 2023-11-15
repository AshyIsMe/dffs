#!/usr/bin/env python3
from __future__ import print_function, absolute_import, division

import logging
import osquery
import json
import polars as pl

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

if not hasattr(__builtins__, 'bytes'):
    bytes = str

OSQUERY_TABLES = [
    "acpi_tables", "apparmor_events", "apparmor_profiles", "apt_sources", "arp_cache",
    "atom_packages", "augeas", "authorized_keys", "azure_instance_metadata",
    "azure_instance_tags", "block_devices", "bpf_process_events", "bpf_socket_events",
    "carbon_black_info", "carves", "certificates", "chrome_extension_content_scripts",
    "chrome_extensions", "cpu_info", "cpu_time", "cpuid", "crontab", "curl",
    "curl_certificate", "deb_packages", "device_file", "device_hash", "device_partitions",
    "disk_encryption", "dns_resolvers", "docker_container_envs", "docker_container_fs_changes",
    "docker_container_labels", "docker_container_mounts", "docker_container_networks",
    "docker_container_ports", "docker_container_processes", "docker_container_stats",
    "docker_containers", "docker_image_history", "docker_image_labels", "docker_image_layers",
    "docker_images", "docker_info", "docker_network_labels", "docker_networks",
    "docker_version", "docker_volume_labels", "docker_volumes",
    #"ec2_instance_metadata",
    #"ec2_instance_tags",
    "etc_hosts", "etc_protocols", "etc_services", "extended_attributes", "file", "file_events",
    "firefox_addons", "groups", "hardware_events", "hash", "intel_me_info",
    "interface_addresses", "interface_details", "interface_ipv6", "iptables", "kernel_info",
    "kernel_keys", "kernel_modules", "known_hosts", "last", "listening_ports", "load_average",
    "logged_in_users", "lxd_certificates", "lxd_cluster", "lxd_cluster_members", "lxd_images",
    "lxd_instance_config", "lxd_instance_devices", "lxd_instances", "lxd_networks",
    "lxd_storage_pools", "magic", "md_devices", "md_drives", "md_personalities",
    "memory_array_mapped_addresses", "memory_arrays", "memory_device_mapped_addresses",
    "memory_devices", "memory_error_info", "memory_info", "memory_map", "mounts",
    "msr", "npm_packages", "oem_strings", "os_version", "osquery_events", "osquery_extensions",
    "osquery_flags", "osquery_info", "osquery_packs", "osquery_registry", "osquery_schedule",
    "pci_devices", "platform_info", "portage_keywords", "portage_packages", "portage_use",
    "process_envs", "process_events", "process_file_events", "process_memory_map",
    "process_namespaces", "process_open_files", "process_open_pipes", "process_open_sockets",
    "processes", "prometheus_metrics", "python_packages", "routes", "rpm_package_files",
    "rpm_packages", "seccomp_events", "secureboot", "selinux_events", "selinux_settings",
    "shadow", "shared_memory", "shell_history", "smbios_tables", "socket_events",
    "ssh_configs", "startup_items", "sudoers", "suid_bin", "syslog_events", "system_controls",
    "system_info", "systemd_units", "time", "ulimit_info", "uptime", "usb_devices",
    "user_events", "user_groups", "user_ssh_keys", "users", "yara", "yara_events",
    "ycloud_instance_metadata", "yum_sources"
]

class Memory(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'

    def __init__(self):
        self.files = {}
        self.data = defaultdict(bytes)
        self.fd = 0
        self.osqueryi = osquery.SpawnInstance()

        self.osqueryi.open()
        now = time()
        self.files['/'] = dict(
            st_mode=(S_IFDIR | 0o755),
            st_ctime=now,
            st_mtime=now,
            st_atime=now,
            st_nlink=2)

        for t in OSQUERY_TABLES:
            self._map_osquery_table(t)

    def chmod(self, path, mode):
        self.files[path]['st_mode'] &= 0o770000
        self.files[path]['st_mode'] |= mode
        return 0

    def chown(self, path, uid, gid):
        self.files[path]['st_uid'] = uid
        self.files[path]['st_gid'] = gid

    def create(self, path, mode):
        self.files[path] = dict(
            st_mode=(S_IFREG | mode),
            st_nlink=1,
            st_size=0,
            st_ctime=time(),
            st_mtime=time(),
            st_atime=time())

        self.fd += 1
        return self.fd

    def getattr(self, path, fh=None):
        if path not in self.files:
            raise FuseOSError(ENOENT)

        return self.files[path]

    def getxattr(self, path, name, position=0):
        attrs = self.files[path].get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR

    def listxattr(self, path):
        attrs = self.files[path].get('attrs', {})
        return attrs.keys()

    def mkdir(self, path, mode):
        self.files[path] = dict(
            st_mode=(S_IFDIR | mode),
            st_nlink=2,
            st_size=0,
            st_ctime=time(),
            st_mtime=time(),
            st_atime=time())

        self.files['/']['st_nlink'] += 1

    def open(self, path, flags):
        self.fd += 1
        return self.fd

    def _map_osquery_table(self, table):
        try:
            logging.debug(f"AA DEBUG: {table=}")
            data = self.osqueryi.client.query(f"select * from {table}").response
            json_data = json.dumps(data)
            path = "/" + table + ".json"
            self.create(path, 0o755)
            self.write(path, str(json_data).encode('utf-8'), 0, None)

            df = pl.DataFrame(data=data)
            path = "/" + table + ".arrow"
            self.create(path, 0o755)
            self._write_direct(path, df.write_ipc(None).getvalue())

        except Exception as e:
            logging.debug(f"AA DEBUG: osquery error: {e=}")

    def _write_direct(self, path, data):
        self.data[path] = data
        self.files[path]['st_size'] = len(self.data[path])
        return len(data)


    def read(self, path, size, offset, fh):
        try:
            if path.endswith(".arrow"):
                fformat = ".arrow"
            elif path.endswith(".json"):
                fformat = ".json"
            else:
                raise Exception(f"invalid file format: {path=}")

            table = path.removeprefix("/").removesuffix(fformat)

            logging.debug(f"AA DEBUG: {path=}, {table=}")
            data = self.osqueryi.client.query(f"select * from {table}").response
            if fformat == ".arrow":
                df = pl.DataFrame(data=data)
                self._write_direct(path, df.write_ipc(None).getvalue())
            elif fformat == ".json":
                data = json.dumps(data)
                self._write_direct(path, str(data).encode('utf-8'))
        except Exception as e:
            logging.debug(f"AA DEBUG: osquery error: {e=}")

        return self.data[path][offset:offset + size]

    def readdir(self, path, fh):
        return ['.', '..'] + [x[1:] for x in self.files if x != '/']

    def readlink(self, path):
        return self.data[path]

    def removexattr(self, path, name):
        attrs = self.files[path].get('attrs', {})

        try:
            del attrs[name]
        except KeyError:
            pass        # Should return ENOATTR

    def rename(self, old, new):
        self.data[new] = self.data.pop(old)
        self.files[new] = self.files.pop(old)

    def rmdir(self, path):
        # with multiple level support, need to raise ENOTEMPTY if contains any files
        self.files.pop(path)
        self.files['/']['st_nlink'] -= 1

    def setxattr(self, path, name, value, options, position=0):
        # Ignore options
        attrs = self.files[path].setdefault('attrs', {})
        attrs[name] = value

    def statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    def symlink(self, target, source):
        self.files[target] = dict(
            st_mode=(S_IFLNK | 0o777),
            st_nlink=1,
            st_size=len(source))

        self.data[target] = source

    def truncate(self, path, length, fh=None):
        # make sure extending the file fills in zero bytes
        self.data[path] = self.data[path][:length].ljust(
            length, '\x00'.encode('ascii'))
        self.files[path]['st_size'] = length

    def unlink(self, path):
        self.data.pop(path)
        self.files.pop(path)

    def utimens(self, path, times=None):
        now = time()
        atime, mtime = times if times else (now, now)
        self.files[path]['st_atime'] = atime
        self.files[path]['st_mtime'] = mtime

    def write(self, path, data, offset, fh):
        self.data[path] = (
            # make sure the data gets inserted at the right offset
            self.data[path][:offset].ljust(offset, '\x00'.encode('ascii'))
            + data
            # and only overwrites the bytes that data is replacing
            + self.data[path][offset + len(data):])
        self.files[path]['st_size'] = len(self.data[path])
        return len(data)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mount')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Memory(), args.mount, foreground=True, allow_other=True)
