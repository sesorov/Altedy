"""
Bot configuration file
"""

import json

from typing import Dict, Any
from pathlib import Path
from jsonschema import validate, ValidationError

# pylint: disable = use-dict-literal


DEFAULT_SCHEMA = {
    "type": "object",
    "properties": {
        "BOT": {
            "type": "object",
            "properties": {
                "TOKEN": {
                    "type": "string",
                    "minLenght": 46,
                    "maxLenght": 46
                },
            },
            "required": ["TOKEN"]
        },
    },
    "required": ["BOT"]
}


class ConfigException(Exception):
    """
    Raise when we cannot parse arguments or open json file
    """


class BotConfig:
    """
    Singleton class that stores application settings, defined in json file, as dictionary
    """

    _instance = None
    _properties: Dict[str, Any] = dict()
    _default_file_path = Path(__file__).resolve().parent / "bot_config.json"

    def __new__(cls, *args, **kwargs):  # pylint: disable=unused-argument
        if not BotConfig._instance:
            BotConfig._instance = super(BotConfig, cls).__new__(cls)
        return BotConfig._instance

    def __init__(self, file_path=None):
        if BotConfig._properties:
            return

        self._file_path = file_path or BotConfig._default_file_path
        self._json_data = self._load_from_json()
        BotConfig._properties = {}

        for name, value in self._json_data.items():
            BotConfig._properties[name] = value
        try:
            with open(Path(__file__).resolve().parent / "token", encoding="utf-8") as token:
                if tkn := token.readline():
                    BotConfig._properties['APP']['TOKEN'] = tkn
        except FileNotFoundError:
            pass

    def _load_from_json(self) -> dict:
        try:
            with open(self._file_path, encoding="utf-8") as cfg_file:
                json_conf = json.load(cfg_file)
                validate(json_conf, DEFAULT_SCHEMA)
                return json_conf
        except IOError as err:
            raise ConfigException(f"Cannot open file '{self._file_path}'") from err
        except ValidationError as err:
            raise ConfigException("File default_config.json does not match default_json_schema") from err

    @property
    def properties(self) -> dict:
        """
        :return: config properties as a dictionary
        """
        return self._properties
