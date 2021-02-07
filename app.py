from chalice import Chalice, Cron
import requests
import re
import datetime
import urllib3
import json
import urllib.request
import os

app = Chalice(app_name='sapporo-gomi')

# @app.route('/')
# def index():
#     result = get_target_gomi_phrase()
#     return {'result': result}

@app.schedule(Cron(0, 13, '?', '*', '*', '*'))
def every_hour(event):
    get_target_gomi_phrase()

def get_target_gomi_phrase():
    target_date = datetime.datetime.now() + datetime.timedelta(days=1)
    
    response = requests.get(os.environ['SAPPORO_GOMI_URI'])
    response.encoding = response.apparent_encoding
    full_html = response.text
    # 必要なあたりだけ取得する
    target_lines = [x for x in full_html.splitlines() if "、燃やせるごみは、" in x]
    # タグを除去する
    target_lines = list(map(lambda line: re.sub('<.*>', '', line), target_lines))
    print(target_lines)
    # 当月のレコードに絞る
    this_month = get_year_and_month_phrase(target_date)
    target_part = list(filter(lambda line: this_month in line, target_lines))[0]
    print(target_part)
    knowledge = create_knowledge_dict(target_part, target_date)
    resp = what_type_is_by_knowledge(knowledge, target_date)
    send_slack(resp)
    return "OK"
    
def get_year_and_month_phrase(target_date):
    """
    filterするための当日の"令和X年Y月"の形式で取得する
    """
    reiwa_year = target_date.year - 2018 
    month = target_date.month
    return_phase = "令和" + str(reiwa_year) + "年" + str(month) + "月"
    print(return_phase)
    return return_phase

def create_knowledge_dict(target, target_date):
    knowledge = Knowledge()
    target = re.sub('^.*燃やせるごみは、', '', target)
    part = re.sub('です。.*', '', target)
    print(target)
    print(part)
    knowledge.burnable = get_days_knowledge_every_weeks(part, target_date.year, target_date.month)

    target = re.sub('^.*びん・缶・ペットボトルは', '', target)
    part = re.sub('、.*', '', target)
    print(target)
    print(part)
    knowledge.pet = get_days_knowledge_every_weeks(part, target_date.year, target_date.month)

    target = re.sub('^.*容器包装プラスチックは', '', target)
    part = re.sub('です。.*', '', target)
    print(target)
    print(part)
    knowledge.pla = get_days_knowledge_every_weeks(part, target_date.year, target_date.month)

    target = re.sub('^.*雑がみは', '', target)
    part = re.sub('です。.*', '', target)
    print(target)
    print(part)
    knowledge.paper = get_days_knowledge_days(part)

    target = re.sub('^.*燃やせないごみは', '', target)
    part = re.sub('です。.*', '', target)
    print(target)
    print(part)
    knowledge.no_burnable = get_days_knowledge_days(part)

    target = re.sub('^.*枝・葉・草は', '', target)
    part = re.sub('です。.*', '', target)
    print(target)
    print(part)
    knowledge.kusa = get_days_knowledge_days(part)
    return knowledge

def what_type_is_by_knowledge(knowledge, target_date):
    if target_date.day in knowledge.burnable:
        return "燃えるゴミ"
    elif target_date.day in knowledge.no_burnable:
        return "燃えないゴミ"
    elif target_date.day in knowledge.pla:
        return "プラスチックごみ"
    elif target_date.day in knowledge.pet:
        return "缶・ビン・ペットボトル"
    elif target_date.day in knowledge.paper:
        return "雑紙"
    elif target_date.day in knowledge.kusa:
        return "草ゴミ"
    return "何もない"

def get_days_knowledge_every_weeks(target, year, month):
    """
    knowledge向けの日付リストを作成する
    毎週X曜日という表記の種別用
    """
    return_list = []
    # その月の1日のdatetimeを取得する
    date = datetime.datetime.strptime(str(year) + "-" + str(month) + '-01', "%Y-%m-%d")
    while True:
        if date.month != month:
            break
        for yobi_idx, yobi in { 0:"月", 1:"火", 2:"水", 3:"木", 4:"金"}.items():
            if yobi in target and yobi_idx == date.weekday():
                return_list.append(date.day)
                break
        date = date + datetime.timedelta(days=1)
    print(return_list)
    return return_list

def get_days_knowledge_days(target):
    """
    knowledge向けの日付リストを作成する
    X日、Y日とあるケース
    """
    if "ありません" in target:
        return []
    day_list = target.split('日、')
    day_list = list(map(lambda line: re.sub('[^0-9]', '', line), day_list))
    print(day_list)
    return day_list

class Knowledge:
    burnable = []
    no_burnable = []
    pla = []
    pet = []
    paper = []
    kusa = []

def create_slack_body(target):
    if target == "何もない":
        return
    return "明日は、" + target + "です。" 

def send_slack(body):
    body = create_slack_body(body)
    url = os.environ["SLACK_WEBHOOK"]
    msg = {
        "channel": "#iwama_gomi",
        "username": "札幌ごみの日",
        "text": body,
        "icon_emoji": ""
    }

    headers = {
        'Content-Type': 'application/json',
    }
    req = urllib.request.Request(url, json.dumps(msg).encode(), headers, method='POST')
    urllib.request.urlopen(req)
