# Main entrypoint
from requests import Request, Session
import json
import lxml.html as lh
import html
from time import sleep
from datetime import datetime
import yagmail
from difflib import unified_diff
import os

s = Session()
maplewood_url = os.environ['MAPLEWOOD_URL']
yag = yagmail.SMTP(os.environ['NOTIFIER_EMAIL'], os.environ['NOTIFIER_KEY'])
update_email = os.environ['USER_EMAIL']
login_details = {}


def get_login_details():
    with open('credentials.json') as file:
        data = json.load(file)
        if 'username' in data and 'password' in data:
            return data
        else:
            raise Exception('Missing username or password in credentials.json!')


def login(username, password):
    s.get(maplewood_url + 'login/login.aspx?logintype=S')
    data = 'EntryType=StudentParent&username=' + username + '&pwd=' + password
    request = Request('POST', maplewood_url + 'login/VerUser.aspx', data=data)
    prepared = s.prepare_request(request)
    prepared.headers['Content-type'] = 'application/x-www-form-urlencoded'
    response = s.send(prepared)
    if response.ok:
        return response.history[0].headers.get('location').endswith('SvrMsg.aspx')
    else:
        raise response.raise_for_status()


def get_markbook_list():
    page = s.get(maplewood_url + 'Viewer/main.aspx')
    tree = lh.fromstring(page.content)
    return tree.xpath('//a/@onclick')[:-1]  # Removes last element from array


def clean_markbook(markbook):
    return markbook[13:-2].split(',')[:-2]


def request_markbook(info):
    data = {
        "studentID": info[0],
        "classID": info[1],
        "termID": info[2],
        "topicID": info[3],
        "fromDate": "1/1/2000",
        "toDate": "1/1/3000",
        "relPath": "../../../",
        "stuLetters": "",
        "orgID": -1
    }
    request = s.prepare_request(Request('POST', maplewood_url + 'Achieve/TopicBas/StuMrks.aspx/GetMarkbook', json=data))
    request.headers['Content-type'] = 'application/json; charset=UTF-8'
    response = s.send(request)
    if response.ok:
        data = response.json().get('d')
        if data.startswith('Unauthorized'):
            print('Token no longer works, logging in...')
            login(login_details['username'], login_details['password'])
            return request_markbook(info)
        else:
            return data
    else:
        response.raise_for_status()


def diff_markbooks(old, new):
    diff = ''
    for line in unified_diff(old.split('\n'), new.split('\n'), n=5000):
        for prefix in ('---', '+++', '@@'):
            if line.startswith(prefix):
                break
        else:
            diff += html.escape(line) + '<br>'
    return diff


def compare_markbooks(markbooks):
    for i in range(len(markbooks)):
        current_markbook = request_markbook(markbookInfo[i])
        if current_markbook != markbooks[i]:
            print(time + ' - Mismatch in index ' + str(i))
            yag.send(update_email, 'Maplewood has been updated!', diff_markbooks(markbooks[i], current_markbook))
            markbooks[i] = current_markbook
        else:
            print(time + ' - No mismatch in index ' + str(i))
    return markbooks


def grab_markbooks(markbookInfo):
    markbooks = []
    for markbook in markbookInfo:
        markbooks.append(request_markbook(markbook))
    return markbooks


if __name__ == '__main__':
    login_details = get_login_details()
    print(login_details['username'])
    if not login(login_details['username'], login_details['password']):
        print('Could not login!')

    markbookInfo = tuple(map(clean_markbook, get_markbook_list()))
    markbooks = grab_markbooks(markbookInfo)

    print('Done initialization')

    num_intervals = 0

    while True:
        time = datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)")
        num_intervals += 1
        if num_intervals % 24 == 0:
            num_intervals = 0
            print(time + ' - Logging into Maplewood again')
            if not login(login_details['username'], login_details['password']):
                yag.send(update_email, 'Could not login to Maplewood!', ':(')
                sleep(600)
                continue
            else:
                print(time + ' - Logged in!')
                markbooks = compare_markbooks(markbooks) # Compare current list
                markbookInfo = tuple(map(clean_markbook, get_markbook_list()))
                markbooks = grab_markbooks(markbookInfo)  # Re-grab markbook list
                sleep(300)

        markbooks = compare_markbooks(markbooks)
        sleep(300)
