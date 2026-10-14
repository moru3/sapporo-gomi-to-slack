from chalice import Chalice, Cron
import requests
import re
import datetime
import urllib3
import json
import urllib.request
import os
import traceback

app = Chalice(app_name='sapporo-gomi')

# @app.route('/')
# def index():
#     result = get_target_gomi_phrase()
#     return {'result': result}

@app.schedule(Cron(0, 13, '?', '*', '*', '*'))
def every_hour(event):
    try:
        get_target_gomi_phrase()
    except Exception as e:
        # 失敗に気づけるようにSlackへ通知する（リトライで重複通知しないよう再送出はしない）
        traceback.print_exc()
        post_slack("ごみ収集日の取得に失敗しました。カレンダーページの形式が変わった可能性があります。(" + repr(e) + ")")

def get_target_gomi_phrase():
    target_date = datetime.datetime.now() + datetime.timedelta(days=1)
    
    response = requests.get(os.environ['SAPPORO_GOMI_URI'])
    response.encoding = response.apparent_encoding
    full_html = response.text
    # 必要なあたりだけ取得し、タグを除去する
    target_lines = [re.sub('<[^>]*>', '', x).strip() for x in full_html.splitlines()
                    if "燃やせるごみは、" in x or "雑がみは" in x]
    print(target_lines)
    # 毎週収集のごみ（燃やせるごみ・びん缶ペット・プラ）は全月共通の1行に書かれている
    weekly_part = [x for x in target_lines if x.startswith("燃やせるごみは、")]
    # 週替わりのごみ（雑がみ・燃やせないごみ・枝葉草）は月ごとの行に書かれている
    this_month = get_year_and_month_phrase(target_date)
    month_part = [x for x in target_lines if x.startswith(this_month + "の、")]
    if not weekly_part or not month_part:
        raise ValueError(this_month + "の収集日が見つかりません")
    target_part = weekly_part[0] + month_part[0]
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
    year = target_date.year
    month = target_date.month
    holidays = get_holidays(target, year, month)

    knowledge.burnable = get_days_knowledge_every_weeks(get_every_weeks_part(target, '燃やせるごみは、'), year, month, holidays)
    knowledge.pet = get_days_knowledge_every_weeks(get_every_weeks_part(target, 'びん・缶・ペットボトルは'), year, month, holidays)
    knowledge.pla = get_days_knowledge_every_weeks(get_every_weeks_part(target, '容器包装プラスチックは'), year, month, holidays)

    knowledge.paper = get_days_knowledge_days(get_days_part(target, '雑がみ'))
    knowledge.no_burnable = get_days_knowledge_days(get_days_part(target, '燃やせないごみ'))
    knowledge.kusa = get_days_knowledge_days(get_days_part(target, '枝・葉・草'))
    return knowledge

def get_every_weeks_part(target, label):
    """
    「燃やせるごみは、毎週火曜日と金曜日です」から「毎週火曜日と金曜日」を取り出す
    """
    match = re.search(label + '(毎週[^、。]*)', target)
    if match is None:
        raise ValueError(label + "の収集曜日が見つかりません")
    part = re.sub('です$', '', match.group(1))
    print(part)
    return part

def get_days_part(target, label):
    """
    「雑がみは8日、22日の木曜日です。」から「は8日、22日の木曜日です」を取り出す
    「枝・葉・草の収集はありません。」の場合は「の収集はありません」になる
    """
    match = re.search(label + '([はの][^。]*)。', target)
    if match is None:
        raise ValueError(label + "の収集日が見つかりません")
    print(match.group(1))
    return match.group(1)

def get_holidays(target, year, month):
    """
    「年末年始期間の12月30日から1月3日までは収集はありません」の期間のうち、対象月の日付リストを返す
    """
    match = re.search(r'(\d+)月(\d+)日から(\d+)月(\d+)日までは収集はありません', target)
    if match is None:
        return []
    start_month, start_day, end_month, end_day = map(int, match.groups())
    result = []
    if month == start_month:
        result += [d for d in range(start_day, 32) if start_month != end_month or d <= end_day]
    if month == end_month and start_month != end_month:
        result += list(range(1, end_day + 1))
    print(result)
    return result

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

def get_days_knowledge_every_weeks(target, year, month, holidays=[]):
    """
    knowledge向けの日付リストを作成する
    毎週X曜日という表記の種別用（holidaysの日は除く）
    """
    return_list = []
    # その月の1日のdatetimeを取得する
    date = datetime.datetime.strptime(str(year) + "-" + str(month) + '-01', "%Y-%m-%d")
    while True:
        if date.month != month:
            break
        for yobi_idx, yobi in { 0:"月", 1:"火", 2:"水", 3:"木", 4:"金"}.items():
            if yobi in target and yobi_idx == date.weekday() and date.day not in holidays:
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
    result = []
    for d in day_list:
        digits = re.sub('[^0-9]', '', d)
        if digits:
            result.append(int(digits))
    print(result)
    return result

class Knowledge:
    def __init__(self):
        self.burnable = []
        self.no_burnable = []
        self.pla = []
        self.pet = []
        self.paper = []
        self.kusa = []

def create_slack_body(target):
    if target == "何もない":
        return
    return "明日は、" + target + "です。" 

def send_slack(body):
    body = create_slack_body(body)
    if body is None:
        return
    post_slack(body)

def post_slack(body):
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
