from flask import render_template
from datetime import date, timedelta

from models import *
from helpers import send_email


def main():
    neardue = Disk.select().where(
        Disk.avail_type == 'Borrowed',
        Disk.due_at == date.today() + timedelta(2)
    )
    for disk in neardue:
        last_log = Log.select().where(Log.model == 'Disk', Log.model_refer == disk.id, Log.Type == 'borrow', Log.user_affected == disk.borrowed_by).order_by(Log.created_at.desc()).get()
        body = render_template('reminder.html', disk=disk, renewable='renew' not in last_log.content)
        send_email([disk.borrowed_by.itsc + '@ust.hk'], ['su_film@ust.hk'], 'Reminder to return disk', body)
    overdue = Disk.select().where(
        Disk.avail_type == 'Borrowed',
        Disk.due_at < date.today()
    )
    for disk in overdue:
        passed = date.today() - Disk.due_at
        if passed.days % 3 == 1:
            body = render_template('overdue.html', disk=disk)
            send_email([disk.borrowed_by.itsc + '@ust.hk'], ['su_film@ust.hk'], 'Reminder to return overdue disk', body)
    reserved = Disk.select().where(Disk.avail_type == 'Reserved')
    for disk in reserved:
        reserve_log = Log.select().where(Log.model == 'Disk', Log.model_refer == disk.id, Log.Type == 'reserve', Log.user_affected == disk.borrowed_by).order_by(Log.created_at.desc()).get()
        if date.today() - reserve_log.created_at.date() > timedelta(2):
            disk.reserved_by = None
            disk.avail_type = 'Available'
            disk.save()
            Log.create(model="Disk", model_refer=disk.id, Type="reserve", content="clear reservation for disk %s(automatically)" % disk.get_callnumber())

if __name__ == '__main__':
    main()
