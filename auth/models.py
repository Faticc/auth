from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path


@dataclass
class Skin:
    url: str
    digest_hex: str = ''


@dataclass
class Cloak:
    url: str
    digest_hex: str = ''


@dataclass
class Profile:
    uuid: str
    username: str
    skin_url: str


@dataclass
class PlayerProfile:
    username: str
    uuid: str
    skin: Optional[Skin] = None
    cloak: Optional[Cloak] = None


@dataclass
class ClientProfile:
    version: str
    asset_index: str
    client_args: List[str]
    server_address: Optional[str] = None
    server_port: Optional[int] = None


@dataclass
class Params:
    pp: PlayerProfile
    access_token: str
    client_dir: Path
    asset_dir: Path
    auto_enter: bool = False
    full_screen: bool = False
    width: int = 0
    height: int = 0