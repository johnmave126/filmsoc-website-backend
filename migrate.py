from app import db
from models import *

import MySQLdb


def migrate(record):
    callnumber = record[0]
    name_ch = record[1]
    name_en = record[2]
    desc_ch = record[3]

    Type = callnumber[0]
    id = int(callnumber[1:])

    log = Log.create(model="Disk", Type='create', model_refer=id, user_affected=None, admin_involved=None, content="import disk %s" % callnumber)
    disk = Disk(id=id, disk_type=Type, title_en=name_en, title_ch=name_ch, desc_ch=desc_ch, show_year=0, avail_type='Available', create_log=log)
    print disk.id
    disk._meta.auto_increment = False
    try:
        disk.save(force_insert=True)
    except MySQLdb.Error:
        log.model_refer = Disk.next_primary_key()
        log.content = "import disk %s%s from %s(callnumber changed)" % (Type, log.model_refer, callnumber)
        disk._meta.auto_increment = True
        disk.save(force_insert=True)
        disk._meta.auto_increment = False
        log.save()


# migrate disk
def main():
    try:
        conn = MySQLdb.connect(host='localhost', user='root', passwd='sflsbug5', db='old_film', charset='utf8')
        cursor = conn.cursor()
        cursor.execute("select `Call_Number` AS `callnumber`, `Name_CHN` AS `name_ch`, `Name_ENG` AS `name_en`, `Describ` AS `desc_ch` from `disc` ORDER BY `callnumber` ASC")
        rset = cursor.fetchall()
        for res in rset:
            migrate(res)
        cursor.close()
        conn.close()
    except MySQLdb.Error, e:
        print "Mysql Error %d: %s" % (e.args[0], e.args[1])

if __name__ == '__main__':
    main()
