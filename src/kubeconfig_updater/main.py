#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
from typing import Dict, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.prompt import Prompt
from rich.theme import Theme
from rich.traceback import install

from kubeconfig_updater.schema import ClusterConfig, KubeConfig, UserConfig, UserEntry

install(show_locals=True)

# Initialize rich console with custom theme
console = Console(
    theme=Theme(
        {"info": "cyan", "warning": "yellow", "error": "red bold", "success": "green"}
    )
)


def parse_hostname(server_url: str) -> Optional[str]:
    m = re.match(r"https?://([^:]+)(:\d+)?", server_url)
    if m:
        return m.group(1)
    return None


def get_server_username(cluster_info: ClusterConfig, host: str) -> str:
    """Get username for SSH connection to server."""
    # First check if we have saved username
    if "serveruser" in cluster_info:
        return cluster_info["serveruser"]

    # Ask user for username using rich prompt
    username = Prompt.ask(f"Enter SSH username for [cyan]{host}[/cyan]")
    return username


def ssh_fetch_admin_conf(
    host: str,
    username: str,
    env: Optional[Dict[str, str]] = None,
    status: Optional[Progress] = None,
) -> Optional[str]:
    try:
        # Use the passed status object instead of creating a new one
        status_message = f"Reading admin.conf from {host} as {username}..."
        if status:
            status.update(status.task_ids[0], description=status_message)
        else:
            console.print(status_message)

        # First try reading directly without sudo
        result = subprocess.run(
            ["ssh", f"{username}@{host}", "cat /etc/kubernetes/admin.conf"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )

        # If direct read succeeds
        if result.returncode == 0:
            return result.stdout

        # If sudo privileges are required
        if status:
            console.print(
                f"Sudo privileges required to read admin.conf from [cyan]{host}[/cyan]"
            )
            sudo_password = Prompt.ask(
                f"Enter sudo password for {username}@{host}", password=True
            )
        else:
            console.print(
                f"Sudo privileges required to read admin.conf from [cyan]{host}[/cyan]"
            )
            sudo_password = Prompt.ask(
                f"Enter sudo password for {username}@{host}", password=True
            )

        # Create script content that will be embedded in the command
        askpass_script = f"""#!/bin/sh
echo '{sudo_password}'
"""

        # Combine all commands into a single SSH session
        sudo_cmd = (
            # Create temporary directory with cleanup trap
            "XDIR=$(mktemp -d /tmp/askpass_XXXXXX); "
            'trap "rm -rf $XDIR" EXIT; '
            # Create askpass script
            f'echo "{askpass_script}" > "$XDIR/askpass.sh"; '
            'chmod 700 "$XDIR/askpass.sh"; '
            # Use the askpass script to read admin.conf
            'export SUDO_ASKPASS="$XDIR/askpass.sh"; '
            "sudo -A cat /etc/kubernetes/admin.conf"
        )

        result = subprocess.run(
            ["ssh", f"{username}@{host}", sudo_cmd],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode != 0:
            console.print(
                f"[error]Unable to read /etc/kubernetes/admin.conf from {host}[/error]"
            )
            console.print(f"[error]Error output: {result.stderr}[/error]")
            return None

        return result.stdout

    except Exception as e:
        console.print(f"[error]Error connecting to {host}: {str(e)}[/error]")
        return None


def backup_file(filepath: str) -> None:
    backup_path = filepath + ".bak"
    shutil.copy(filepath, backup_path)
    console.print(f"[info]Backup created at {backup_path}[/info]")


def main() -> None:
    console.print(
        Panel.fit(
            "Kubernetes Config Updater",
            style="bold cyan",
        )
    )

    kubeconfig_path = os.path.expanduser("~/.kube/config")
    # Read local kubeconfig
    try:
        with open(kubeconfig_path, "r") as f:
            local_config: KubeConfig = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[error]Error reading {kubeconfig_path}: {str(e)}[/error]")
        return

    backup_file(kubeconfig_path)

    # Extract clusters, contexts and users sections with proper typing
    clusters: Dict[str, ClusterConfig] = {
        item["name"]: item["cluster"] for item in local_config.get("clusters", [])
    }
    users: Dict[str, UserConfig] = {
        item["name"]: item["user"] for item in local_config.get("users", [])
    }
    contexts = local_config.get("contexts", [])

    # Track update status
    updated_contexts = []

    console.print(f"[info]Total contexts to process: {len(contexts)}")

    for idx, ctx in enumerate(contexts, start=1):
        context_name = ctx.get("name")
        ctx_details = ctx.get("context", {})
        cluster_name = ctx_details.get("cluster")
        user_name = ctx_details.get("user")

        console.print(f"[info]Processing context {idx}/{len(contexts)}: {context_name}")

        if not (cluster_name and user_name):
            console.print(
                f"[warning]Skipping context {context_name} due to missing cluster/user data[/warning]"
            )
            continue

        if not (cluster_info := clusters.get(cluster_name)):
            console.print(
                f"[warning]Cannot find cluster {cluster_name} configuration, skipping context {context_name}[/warning]"
            )
            continue

        if not (server_url := cluster_info.get("server")):
            console.print(
                f"[warning]Cluster {cluster_name} missing server field, skipping context {context_name}[/warning]"
            )
            continue

        if not (host := parse_hostname(server_url)):
            console.print(
                f"[warning]Cannot parse hostname from server URL {server_url}, skipping context {context_name}[/warning]"
            )
            continue

        # Get username for this server
        username = get_server_username(cluster_info, host)
        cluster_info["serveruser"] = username

        # Set LC_ALL=C to avoid locale issues
        env = os.environ.copy()
        env["LC_ALL"] = "C"

        # Fetch admin.conf from the remote server
        if not (admin_conf_text := ssh_fetch_admin_conf(host, username, env)):
            continue

        try:
            remote_conf = yaml.safe_load(admin_conf_text)
        except Exception as e:
            console.print(f"[error]Error parsing admin.conf from {host}: {e}[/error]")
            continue

        if not (remote_users := remote_conf.get("users", [])):
            console.print(
                f"[warning]No user data in admin.conf from remote {host}, skipping[/warning]"
            )
            continue

        remote_user = remote_users[0]
        remote_cert = remote_user.get("user", {}).get("client-certificate-data")
        remote_key = remote_user.get("user", {}).get("client-key-data")
        if not (remote_cert and remote_key):
            console.print(
                f"[warning]No client certificate data found in admin.conf from remote {host}, skipping[/warning]"
            )
            continue

        if not (local_user := users.get(user_name)):
            console.print(
                f"[warning]Cannot find user {user_name} in local kubeconfig, skipping[/warning]"
            )
            continue

        changed = False
        if local_user.get("client-certificate-data") != remote_cert:
            console.print(
                f"[info]updating {user_name}'s client-certificate-data[/info]"
            )
            local_user["client-certificate-data"] = remote_cert
            changed = True
        if local_user.get("client-key-data") != remote_key:
            console.print(f"[info]updating {user_name}'s client-key-data[/info]")
            local_user["client-key-data"] = remote_key
            changed = True

        if changed:
            updated_contexts.append(context_name)
            local_config["users"] = [
                UserEntry(name=name, user=user_data)
                for name, user_data in users.items()
            ]

    try:
        if updated_contexts:
            with open(kubeconfig_path, "w") as f:
                yaml.safe_dump(local_config, f, sort_keys=False)
            console.print("[success]Updated ~/.kube/config[/success]")
            console.print(
                "[success] Credentials updated for the following contexts:[/success]"
            )
            for ctx in updated_contexts:
                console.print(f"[success] - {ctx}[/success]")
        else:
            console.print("[info]All credentials are up-to-date[/info]")
    except Exception as e:
        console.print(f"[error]Error writing to {kubeconfig_path}: {str(e)}[/error]")


def cli():
    """Entry point for the command-line interface."""
    main()


if __name__ == "__main__":
    cli()
