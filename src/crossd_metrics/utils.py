# -*- coding=utf-8 -*-
import re

regex = r"(?:(?:https?|ftp|file):\/\/|www\.|ftp\.)(?:\([-A-Z0-9+&@#\/%=~_|$?!:,.]*\)|[-A-Z0-9+&@#\/%=~_|$?!:,.])*(?:\([-A-Z0-9+&@#\/%=~_|$?!:,.]*\)|[A-Z0-9+&@#\/%=~_|$])"
pattern = re.compile(regex, re.IGNORECASE | re.MULTILINE)


def get_readme_index(name: str) -> str:
    return name.replace(".", "_").replace("/", "_")


def get_urls(content: str) -> [str]:
    return pattern.findall(content)