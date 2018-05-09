import json
from pathlib import Path

import pandas as pd
from lxml import etree
from requests import session
from requests.utils import cookiejar_from_dict

import pandas as pd


class CricMarketOption:
    city = '南京'
    trade_source = '1类'
    time_type = 'Month'  # Day, Week, Month, Quater, Year
    time = '2018年01月:2018年05月'  # 2018-01-01, 2018年01周, 2018年01月, 2018年03季度, 2018年, 开始、结束用冒号分隔
    region_type = 'Region'  # Region:区域, District:板块, Circle:环线
    region = ''  # 多个值用逗号分隔
    usage = '普通住宅,别墅'  # 普通住宅, 别墅, 酒店式公寓, 商业, 办公, 多个值用逗号分隔
    rows = 'time'  # time, region, RoomUsage, Step.AreaStep, Step.PriceStep, Step.AllMoneyStep
    columns = []  # 同rows
    outputs = '供应面积,成交面积,成交均价'  # 供应面积 供应套数 成交面积 成交套数 成交均价 套均价 成交金额 供求比 环比 同比
    rowtotal = False

    @property
    def data(self):
        params = {
            "Dims": [
                # 城市
                {"Key": "MarketMonitor.Dim.City",
                 "Value": self.city},
                # TradeSource 作用未知
                {"Key": "MarketMonitor.Dim.TradeSource",
                 "Value": self.trade_source},
                # 统计时间类型：每日, 周度, 月度, 季度, 年度
                {"Key": f"MarketMonitor.Dim.Time.{self.time_type}",
                 "Value": self.time},
                # 物业类型
                {"Key": "MarketMonitor.Dim.RoomUsage",
                 "Value": self.usage}
            ],
            # 列分类依据，默认为空
            "Columns": [f"MarketMonitor.Dim.{x}" for x in self.columns],
            # 输出项
            "Outputs": self.outputs,
            # 是否显示合计行，默认不显示
            "RowTotal": self.rowtotal
        }

        # 地域筛选类别 与 筛选关键词
        if self.region:
            params['Dims'].append({
                "Key": f"MarketMonitor.Dim.Region.{self.region_type}",
                "Value": self.region
            })

        # 行分类依据 按时间, 地区, 或其他
        if self.rows == 'time':
            params['Rows'] = [f"MarketMonitor.Dim.Time.{self.time_type}"]
        elif self.rows == 'region':
            params['Rows'] = [f"MarketMonitor.Dim.Region.{self.region_type}"]
        else:
            params['Rows'] = [f"MarketMonitor.Dim.{x}" for x in self.rows]

        # 返回一个嵌套字典，作为post传递的数据
        return {
            'paramStr': json.dumps(params, ensure_ascii=False),
            'cityName': self.city,
            'tableConfig': 'Date',
            'MenuKey': 100010
        }


class CricLandOption:
    by = 'time'  # time, city,
    province = '江苏省'
    city = '南京'
    region = ''
    district = ''
    date_type = '月度'  # 月度, 季度, 年度
    date = '2018年01月:2018年05月'
    state = '成交'  # 成交, 供应
    method = '招拍挂土地'  # 协议土地, 招拍挂土地, 其他出让土地
    usage = '纯住宅,商住'  # 纯住宅, 商住, 商办, 综合用地, 工业, 其他

    @property
    def data(self):
        # 基本筛选项
        data = [['PROVINCE', 'PROVINCE', self.province],
                ['CITY_NAME', 'CITY_NAME', self.city],
                ['BIDDING_DATE', self.date_type, ''],
                ['LAND_TRADE_STATE', '', self.state],
                ['BIDDING_METHOD', '', self.method],
                ['USE_TYPE_TAG', '', self.usage]]

        # 区域和板块筛选
        if self.region:
            data.append(['REGION', 'REGION', self.region])
        if self.district:
            data.append(['DISTRICT', 'DISTRICT', self.district])

        # 生成
        df = pd.DataFrame(data, columns=['Key', 'Tag', 'Value'])

        # 日期筛选
        start, end = self.date.split(':')
        df['MinValue'], df['MaxValue'], df['Type'] = '', '', ''
        df.loc[df.Key == 'BIDDING_DATE', ['MinValue', 'MaxValue', 'Type']] = start, end, 'Date'

        # 返回一个嵌套字典，作为post传递的数据
        by = {'time': ('按时间', 200002), 'city': ('按城市', '200003')}
        return {
            'strParam': json.dumps(df.to_dict('record'), ensure_ascii=False),
            'tablestyle': '交叉模式',
            'tablefield': 'PROPERTY',
            'statistictype': by[self.by][0],
            'statisticdetailtitle': f'{start}至{end}土地{self.state}明细',
            'MenuKey': by[self.by][1]
        }


class Cric:
    s = session()
    path = Path('cric.txt')

    def __init__(self):
        if not self.path.exists():
            self._get_cookie()
        self._login()

    def _get_cookie(self):
        from selenium import webdriver
        self.driver = webdriver.Chrome()
        self.driver.get('http://app.cric.com/')
        input('[*] 登陆完成后按回车保存cookies...\n')
        cookie_1 = self.driver.get_cookie('cric2015_token')['value']
        cookie_2 = self.driver.get_cookie('cric2015')['value']
        self.path.write_text('\n'.join([cookie_1, cookie_2]))

    def _login(self):
        cookie_1, cookie_2 = self.path.read_text().split('\n')
        cookies = {'cric2015_token': cookie_1, 'cric2015': cookie_2}
        self.s.cookies = cookiejar_from_dict(cookies)
        self.s.headers.update({'Host': 'app.cric.com'})

    def relogin(self):
        if self.path.exists():
            self.path.unlink()
        self._get_cookie()
        self._login()

    def _post(self, url, data):
        return self.s.post(url, data).text

    def market(self, data):
        html = self._post('https://app.cric.com/Statistic/MarketMonitor/GetComprehensiveTableData', data)
        return self._html2df(html)

    def land(self, data):
        html = self._post('https://app.cric.com/land/Statistic/Statistic/StatisticTable', data)
        return pd.read_html(html, index_col=0, header=0)[0]

    @staticmethod
    def _html2df(html):
        tree = etree.HTML(html)
        left = tree.cssselect('#LeftDiv')[0]
        right = tree.cssselect('#RightDiv')[0]

        # index 找出左div中所有含rowno属性的标签，每个标签下class='text'的标签的文字
        rows = left.cssselect('[rowno]')
        index = [x.cssselect('.text')[0].text for x in rows]

        # columns 找出右div第一个tbody，里面第个th标签的文字代表表头
        columns = right.cssselect('tbody')[0].cssselect('th')
        columns = [x.text for x in columns]

        # values 找出右div中所有含rowno属性的标签，将每行展开成一个'td'表签列表，每个td取文字
        rows = right.cssselect('[rowno]')
        df = pd.DataFrame([x.cssselect('td') for x in rows], index, columns)
        df = df.applymap(lambda x: x.text.strip().replace(',', ''))

        return df
