import re

from peewee import *
from flask import render_template

from models import *

__all__ = ["BBCode"]


class BBCode(object):
    """A BBCode parser
    """

    def __init__(self):
        # predefined BB Code set
        self.BBHandler = [
            {"pattern": r"\[b\](.+?)\[/b\]", "repl": '<b>\1</b>'},
            {"pattern": r"\[i\](.+?)\[/i\]", "repl": '<em>\1</em>'},
            {"pattern": r"\[u\](.+?)\[/u\]", "repl": '<u>\1</u>'},
            {"pattern": r"\[big\](.+?)\[/big\]", "repl": '<big>\1</big>'},
            {"pattern": r"\[small\](.+?)\[/small\]", "repl": '<small>\1</small>'},
            {"pattern": r"\[color=([a-zA-Z]*|\#?[0-9a-fA-F]{6})\](.+?)\[/color\]",
                "repl": '<span style="color:\1">\2</span>'},
            {"pattern": (r"\[link=\s*((?:(?:ftp|https?)://)?"
                            "(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
                            "[A-Z]{2,6}\.?|localhost|"
                            "\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
                            "(?::\d+)?(?:/?|[/?]\S+?))\s*\](.+?)\[/link\]"),
                "repl": '<a href="\1" rel="nofollow" target="_blank">\2</a>'},
            {"pattern": (r"\[img=\s*((?:(?:ftp|https?)://)?"
                            "(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
                            "[A-Z]{2,6}\.?|localhost|"
                            "\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
                            "(?::\d+)?(?:/?|[/?]\S+?))\s*\](.*?)\[/img\]"),
                "repl": '<img src="\1" alt="\2" title="\2">'},
            {"pattern": r"\[inlinedisk\](\d+)\[/inlinedisk\]",
                "repl": self.parse_inlinedisk},
            {"pattern": r"\[disk\](\d+)\[/disk\]",
                "repl": self.parse_disk},
            {"pattern": r"\[rfs\](\d+)\[/rfs\]",
                "repl": self.parse_rfs},
            {"pattern": r"\[ticket\](\d+)\[/ticket\]",
                "repl": self.parse_ticket},
        ]

    @staticmethod
    def parse_inlinedisk(matchobj):
        """display disk infomation inline"""
        disk_id = int(matchobj.group(0))
        try:
            disk = Disk.select().where(Disk.id == disk_id).get()
        except DoesNotExist:
            return ""

        return render_template("rich_inlinedisk.html", disk=disk)

    @staticmethod
    def parse_disk(matchobj):
        """display disk infomation"""
        disk_id = int(matchobj.group(0))
        try:
            disk = Disk.select().where(Disk.id == disk_id).get()
        except DoesNotExist:
            return ""

        return render_template("rich_disk.html", disk=disk)

    @staticmethod
    def parse_rfs(matchobj):
        """display rfs infomation"""
        rfs_id = int(matchobj.group(0))
        try:
            rfs = RegularFilmShow.select().where(
                RegularFilmShow.id == rfs_id).get()
        except DoesNotExist:
            return ""

        return render_template("rich_rfs.html", rfs=rfs)

    @staticmethod
    def parse_ticket(matchobj):
        """display ticket infomation"""
        ticket_id = int(matchobj.group(0))
        try:
            ticket = PreviewShowTicket.select().where(
                PreviewShowTicket.id == ticket_id).get()
        except DoesNotExist:
            return ""

        return render_template("rich_ticket.html", ticket=ticket)

    def parse(self, text):
        """parse the text to convert to HTML

        :param text:
            The text to convert
        """
        for parser in self.BBHandler:
            while True:
                old_text = text
                text = re.sub(parser["pattern"], parser["repl"],
                                text, flags=re.I)
                if old_text == text:
                    break

        return text