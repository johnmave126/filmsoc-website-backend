from datetime import date
from models import User
from helpers import update_mailing_list
from string import join

def main():
    user_sq = User.select().where(
    	User.member_type != 'Expired',
    	User.expire_at < date.today()
    )
    print join([(x.itsc + "@ust.hk") for x in user_sq], ';')
    #for user in user_sq:
    #    user.member_type = 'Expired'
    #    user.save()

    #update_mailing_list([x.itsc for x in User.select(User.itsc).where(User.member_type != 'Expired')])

if __name__ == '__main__':
    main()
