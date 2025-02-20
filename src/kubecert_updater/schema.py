from typing import List, Optional, TypedDict


class ClusterConfig(TypedDict):
    server: str
    serveruser: Optional[str]
    certificate_authority_data: Optional[str]


class UserConfig(TypedDict):
    client_certificate_data: str
    client_key_data: str


class ContextDetails(TypedDict):
    cluster: str
    user: str
    namespace: Optional[str]


class Context(TypedDict):
    name: str
    context: ContextDetails


class ClusterEntry(TypedDict):
    name: str
    cluster: ClusterConfig


class UserEntry(TypedDict):
    name: str
    user: UserConfig


class KubeConfig(TypedDict):
    """Kubernetes configuration file schema."""

    apiVersion: str
    clusters: List[ClusterEntry]
    contexts: List[Context]
    current_context: str
    kind: str
    preferences: dict
    users: List[UserEntry]
