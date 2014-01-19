#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# A little script to recalculate the rating of each disk
# The script should be set up as a scheduled task.

from models import *
from helpers import confidence


"""Go through each disk and recalculate the confidence value
"""
def main():
    disk_sq = Disk.select()
    for disk in disk_sq:
        ups, downs = disk.get_rate()
        disk.rank = confidence(ups, downs)
        disk.save()


if __name__ == '__main__':
    main()
