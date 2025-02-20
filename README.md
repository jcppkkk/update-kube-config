# Kubernetes Certificate Updater (update-kube-config)

A tool to automatically update Kubernetes certificate data in your kubeconfig file by connecting to each cluster and fetching the latest credentials.

## Overview

This tool helps maintain your Kubernetes configurations by:
- Scanning your `~/.kube/config` file for all contexts
- Connecting to each Kubernetes cluster via SSH
- Fetching the latest certificate data from `/etc/kubernetes/admin.conf`
- Updating your local kubeconfig with the new credentials
- Saving SSH usernames for future use

## Installation

Install using `uvx` or `uv tool install`:

```bash
uvx install git+https://github.com/jcppkkk/update-kube-config.git
```

or

```bash
uv tool install git+https://github.com/jcppkkk/update-kube-config.git
```

## Usage

Simply run:

```bash
update-kube-config
```

The tool will:
1. Create a backup of your existing kubeconfig
2. Process each context in your kubeconfig
3. Connect to each cluster's server
4. Update certificate data as needed

### First-time Usage

When connecting to a server for the first time, you'll be prompted for:
- SSH username for the server
- Sudo password (if required to read admin.conf)

The SSH username is saved in your kubeconfig for future use under the cluster's `serveruser` field.

### Security

- Creates automatic backups of your kubeconfig before making changes
- Uses SSH for secure remote connections
- Handles sudo access securely when required
- Stores credentials only in your kubeconfig file

## Requirements

- Python 3.8 or higher
- SSH access to your Kubernetes clusters
- Sudo privileges on remote servers (if required)
- Read access to `/etc/kubernetes/admin.conf` on remote servers

## Features

- ✅ Automatic certificate updates
- ✅ Multi-context support
- ✅ SSH username persistence
- ✅ Automatic kubeconfig backups
- ✅ Sudo handling when required
- ✅ Non-interactive mode after initial setup

## Troubleshooting

If you encounter issues:

1. Check SSH access to your clusters
2. Verify sudo privileges if required
3. Ensure `/etc/kubernetes/admin.conf` exists on the remote servers
4. Check the backup file at `~/.kube/config.bak` if needed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License