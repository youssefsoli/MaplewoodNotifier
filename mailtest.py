import yagmail
import os

yag = yagmail.SMTP(os.environ['NOTIFIER_EMAIL'], os.environ['NOTIFIER_KEY'])
update_email = os.environ['USER_EMAIL']

yag.send(update_email, 'Test', 'body')