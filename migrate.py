from app import db
from werkzeug.datastructures import MultiDict
from models import *
from forms import *

import MySQLdb
from datetime import datetime, date
from helpers import query_user, send_email


user_map = {
    "full": "Full",
    "one": "OneYear",
    "two": "TwoYear",
    "ass": "Assoc",
}


def migrate_user(record):
    stuid = record[0]
    itsc = record[1]
    mobile = record[2]
    Type = record[3]
    join_at = record[4]
    expire_at = record[5]

    # convert join_at
    if len(join_at) == 0 or join_at == '0000-00-00':
        join_at = date(2012, 9, 1)
    else:
        try:
            join_at = datetime.strptime(join_at, '%Y-%m-%d')
        except ValueError:
            join_at = datetime.strptime('%s-09-01' % join_at, '%Y-%m-%d')

    # convert expire_at
    if len(expire_at) == 0 or expire_at == '0000-00-00':
        expire_at = date(2016, 9, 1)
    else:
        try:
            expire_at = datetime.strptime(expire_at, '%Y-%m-%d')
        except ValueError:
            expire_at = datetime.strptime('%s-09-01' % expire_at, '%Y-%m-%d')
    # convert Type
    Type = user_map[Type]
    data = {
        'itsc': itsc,
        'student_id': stuid,
        'mobile': mobile,
        'member_type': Type,
        'expire_at': expire_at.strftime('%Y-%m-%d')
    }
    form = UserForm(MultiDict(data))
    if not form.validate():
        Log.create(model="User", model_refer=0, Type='create', content="import error at user %s(%s). Wrong format." % (itsc, stuid))
        return
    user_info = query_user(data.get('itsc', None))
    if not user_info:
        Log.create(model="User", model_refer=0, Type='create', content="import error at user %s(%s). Non-exist ITSC." % (itsc, stuid))
        return
    data['full_name'] = user_info['displayName']
    User.create(**data)


def migrate_disk(record):
    callnumber = record[0]
    name_ch = record[1]
    name_en = record[2]
    desc_ch = record[3]
    image_blob = record[4]

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


# migrate database
def main():
    try:
        conn = MySQLdb.connect(host='localhost', user='film', passwd='filmsoc', db='old_film', charset='utf8')
        cursor = conn.cursor()
        # user
        cursor.execute("select `Stu_ID` AS `stuid`, `ITSC` AS `itsc`, `Mobile` AS `mobile`, `Membership` AS `Type`, `Year_Attend` AS `join_at`, `Valid_Thru` AS `expire_at` from `member`")
        for row in cursor:
            migrate_user(row)
        #disk
        #cursor.execute("select `Call_Number` AS `callnumber`, `Name_CHN` AS `name_ch`, `Name_ENG` AS `name_en`, `Describ` AS `desc_ch`, `Img` AS `image` from `disc` ORDER BY `callnumber` ASC")
        #for row in cursor:
        #    migrate_disk(row)
        cursor.close()
        conn.close()
    except MySQLdb.Error, e:
        print "Mysql Error %d: %s" % (e.args[0], e.args[1])

if __name__ == '__main__':
    main()
