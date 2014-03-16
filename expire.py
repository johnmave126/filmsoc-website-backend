#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# A little script to check member expire date and flag them
# The script should be run at the beginning of each semester.

from datetime import date
from models import User
from helpers import update_mailing_list

"""Check each member and flag the member type. Update the mailling 
list when done
"""
def main():
    user_sq = User.select().where(
        User.member_type != 'Expired',
        User.expire_at < date.today()
    )
    for user in user_sq:
        user.member_type = 'Expired'
        user.save()

    update_mailing_list(
        [x.itsc for x in User.select(User.itsc).where(
            User.member_type != 'Expired')])

if __name__ == '__main__':
    main()
