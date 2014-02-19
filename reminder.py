#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# A little script to send reminders of VCD/DVD Library.
# It also clears reservation of more than 3 days.
# The script should be set up as a scheduled task.

from datetime import date, timedelta
from jinja2 import Environment, PackageLoader

from models import *
from helpers import send_email


def main():
    # Since the script is standalone, we need to first invoke the
    # Jinja template environment
    env = Environment(loader=PackageLoader('filmsoc', 'templates'))

    # Acquire essential templates
    tp_reminder = env.get_template("reminder.html")
    tp_renewed = env.get_template("renewed_reminder.html")
    tp_overdue = env.get_template("overdue.html")

    # Send reminders of disks due the next day
    neardue = Disk.select().where(
        Disk.avail_type == 'Borrowed',
        Disk.due_at == date.today() + timedelta(1)
    )
    for disk in neardue:
        last_log = Log.select().where(
                Log.model == 'Disk',
                Log.model_refer == disk.id,
                Log.log_type == 'borrow',
                Log.user_affected == disk.hold_by
            ).order_by(Log.created_at.desc()).get()
        if 'renew' not in last_log.content:
            body = tp_reminder.render(disk=disk)
            send_email(
                [disk.hold_by.itsc + '@ust.hk'],
                ['su_film@ust.hk'],
                'Reminder: Due Date of the VCD/DVD(s) You Borrowed',
                body)
        else:
            body = tp_renewed.render(disk=disk)
            send_email(
                [disk.hold_by.itsc + '@ust.hk'],
                ['su_film@ust.hk'],
                'Reminder: Due Date of the VCD/DVD(s) You Renewed',
                body)
    
    # Send reminders of disks overdue
    # Sent every 3 days
    overdue = Disk.select().where(
        Disk.avail_type == 'Borrowed',
        Disk.due_at < date.today()
    )
    for disk in overdue:
        passed = date.today() - disk.due_at
        if passed.days % 3 == 1:
            body = tp_overdue.render(disk=disk)
            send_email(
                [disk.hold_by.itsc + '@ust.hk'],
                ['su_film@ust.hk'],
                'Reminder: Overdue of the VCD/DVD(s)',
                body)


    # Clear reservation of disks over 3 days
    # Only clear Counter Reservation
    reserved = Disk.select().where(Disk.avail_type == 'ReservedCounter')
    for disk in reserved:
        reserve_log = Log.select().where(
                Log.model == 'Disk',
                Log.model_refer == disk.id,
                Log.log_type == 'reserve',
                Log.user_affected == disk.reserved_by
            ).order_by(Log.created_at.desc()).get()
        if date.today() - reserve_log.created_at.date() > timedelta(2):
            disk.reserved_by = None
            disk.avail_type = 'Available'
            disk.save()
            Log.create(
                model="Disk",
                model_refer=disk.id,
                log_type="reserve",
                content="clear reservation for disk %s(automatically)" % 
                disk.get_callnumber())

if __name__ == '__main__':
    main()
