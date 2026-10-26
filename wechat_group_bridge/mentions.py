"""Recognize WeChat's actual @ target IDs independently of display names."""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET

from .db_crypto import decompress_content


def match_mention(text, source, compression, self_id, display_name):
    targets = None
    xml = decompress_content(source, compression)
    if isinstance(xml, str) and len(xml) <= 65536 and not re.search(r'<!DOCTYPE|<!ENTITY', xml, re.I):
        try:
            node = ET.fromstring(xml).find('.//atuserlist')
            if node is not None and (node.text or '').strip():
                targets = {value.strip() for value in node.text.split(',') if value.strip()}
        except ET.ParseError:
            pass
    aliases = sorted({name for name in ('师滔', display_name) if name}, key=len, reverse=True)
    pattern = re.compile(r'[@＠](?:' + '|'.join(re.escape(name) for name in aliases) + r')(?=$|[\s:：,，。!！?？])')
    mentioned = self_id in targets if targets is not None else bool(pattern.search(text))
    clean = pattern.sub('', text).strip(' \t\r\n\u2005:：，,。') if mentioned else text
    # A room nickname can differ from the contact nickname. For a single real
    # @ target, WeChat's U+2005 separator identifies the displayed name token.
    if mentioned and targets == {self_id} and clean == text:
        clean = re.sub(r'[@＠][^@＠\r\n\u2005]+\u2005', '', text, count=1).strip(' \t\r\n:：，,。')
    return mentioned, targets is not None, clean
