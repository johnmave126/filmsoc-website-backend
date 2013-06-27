from models import *
from helpers import confidence


def main():
    disk_sq = Disk.select()
    for disk in disk_sq:
        ups, downs = disk.get_rate()
        disk.confidence = confidence(ups, downs)
        disk.save()


if __name__ == '__main__':
    main()
